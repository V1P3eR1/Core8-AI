"""Business Brain REST API (DESIGN.md §6). All routes JWT-protected and tenant-checked.

Logs carry IDs and counts only — never answer values or fact contents.
"""

import json
import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from business_brain import repository
from business_brain.access import TenantAccess, tenant_role, PLATFORM_ADMIN
from business_brain.context import ScopeError, get_agent_context, validate_scope
from business_brain.discovery import AssessmentClosed, submit_answers
from business_brain.opportunities import analyse, brain_answers
from business_brain.plan import build_plan, render_markdown
from business_brain.questionnaire import (
    AnswerError, INTAKE_DOMAIN, active_modules, load_questionnaire, next_question, progress,
)
from business_brain.schema import FACT_CATEGORIES, SENSITIVITY_LEVELS
from security.jwt_auth import get_user_by_email, require_jwt

logger = logging.getLogger("core8.business_brain")

router = APIRouter(tags=["business-brain"], dependencies=[Depends(require_jwt)])

MAX_FACT_CHARS = 20000

viewer = tenant_role("viewer")
editor = tenant_role("editor")
owner = tenant_role("owner")


# ── Models ────────────────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    owner_email: str | None = None


class MemberSet(BaseModel):
    email: str
    role: Literal["owner", "editor", "viewer"]


class AnswersIn(BaseModel):
    answers: dict[str, Any]


class FactIn(BaseModel):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9_.\-]+$")
    category: str
    domain: str = "general"
    value: Any
    sensitivity: str = "internal"


class FeedbackIn(BaseModel):
    fact_id: str
    kind: Literal["correction", "flag", "comment"]
    proposed_value: Any = None
    note: str | None = Field(default=None, max_length=2000)


class FeedbackResolve(BaseModel):
    decision: Literal["accept", "reject"]


class ScopeIn(BaseModel):
    categories: list[str]
    domains: list[str]
    max_sensitivity: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _known_domains() -> list[str]:
    return [INTAKE_DOMAIN] + [m["id"] for m in load_questionnaire().modules]


async def _assessment_or_404(access: TenantAccess, assessment_id: str) -> dict:
    a = await access.repo.get_assessment(assessment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


async def _assessment_view(access: TenantAccess, a: dict) -> dict:
    qn = load_questionnaire()
    answers = await access.repo.get_answers(a["id"])
    nq = next_question(qn, answers)
    return {
        **a,
        "answers": answers,
        "active_modules": active_modules(qn, answers),
        "progress": progress(qn, answers),
        "next_question": _public_q(nq),
    }


def _public_q(q: dict | None) -> dict | None:
    if not q:
        return None
    return {k: q[k] for k in ("id", "text", "type", "required", "options", "max_items", "module") if k in q}


# ── Questionnaire & tenants ──────────────────────────────────────────────────

@router.get("/api/discovery/questionnaire")
async def get_questionnaire():
    return load_questionnaire().public_definition()


@router.post("/api/tenants", status_code=201)
async def create_tenant(req: TenantCreate, user: dict = Depends(require_jwt)):
    """Platform admins create client tenants. The creator becomes an owner of this tenant only;
    other staff get access per client via /members."""
    if user.get("role") != PLATFORM_ADMIN:
        raise HTTPException(status_code=403, detail="Admin role required")
    owners = [user["sub"]]
    if req.owner_email:
        u = await get_user_by_email(req.owner_email)
        if not u:
            raise HTTPException(status_code=404, detail="Owner user not found")
        owners.append(u["id"])
    tenant = await repository.create_tenant(req.name.strip(), user["sub"], owners)
    logger.info("tenant created id=%s by=%s", tenant["id"], user["sub"])
    return tenant


@router.get("/api/tenants")
async def list_tenants(user: dict = Depends(require_jwt)):
    """Only tenants the caller is an explicit member of."""
    return await repository.list_tenants_for_user(user["sub"])


@router.get("/api/admin/tenants")
async def tenant_directory(user: dict = Depends(require_jwt)):
    """Client directory for platform admins: names and member counts only, no Brain data."""
    if user.get("role") != PLATFORM_ADMIN:
        raise HTTPException(status_code=403, detail="Admin role required")
    return await repository.tenant_directory()


@router.get("/api/tenants/{tenant_id}")
async def get_tenant(access: TenantAccess = Depends(viewer)):
    return {**await access.repo.get_tenant(), "your_role": access.role}


@router.get("/api/tenants/{tenant_id}/members")
async def list_members(access: TenantAccess = Depends(owner)):
    return await access.repo.list_members()


@router.post("/api/tenants/{tenant_id}/members")
async def set_member(req: MemberSet, access: TenantAccess = Depends(owner)):
    u = await get_user_by_email(req.email)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    current = await access.repo.get_member_role(u["id"])
    if current == "owner" and req.role != "owner" and await access.repo.count_owners() <= 1:
        raise HTTPException(status_code=409, detail="A tenant must keep at least one owner")
    await access.repo.set_member(u["id"], req.role, granted_by=access.user_id)
    logger.info("tenant member set tenant=%s user=%s role=%s by=%s", access.tenant_id, u["id"], req.role, access.user_id)
    return {"user_id": u["id"], "role": req.role}


@router.delete("/api/tenants/{tenant_id}/members/{user_id}", status_code=204)
async def remove_member(user_id: str, access: TenantAccess = Depends(owner)):
    current = await access.repo.get_member_role(user_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if current == "owner" and await access.repo.count_owners() <= 1:
        raise HTTPException(status_code=409, detail="A tenant must keep at least one owner")
    await access.repo.remove_member(user_id)
    logger.info("tenant member removed tenant=%s user=%s by=%s", access.tenant_id, user_id, access.user_id)


# ── Assessments ──────────────────────────────────────────────────────────────

@router.post("/api/tenants/{tenant_id}/assessments", status_code=201)
async def start_assessment(access: TenantAccess = Depends(editor)):
    a = await access.repo.create_assessment(load_questionnaire().version, access.user_id)
    logger.info("assessment started tenant=%s id=%s", access.tenant_id, a["id"])
    return await _assessment_view(access, a)


@router.get("/api/tenants/{tenant_id}/assessments/{assessment_id}")
async def get_assessment(assessment_id: str, access: TenantAccess = Depends(viewer)):
    return await _assessment_view(access, await _assessment_or_404(access, assessment_id))


@router.put("/api/tenants/{tenant_id}/assessments/{assessment_id}/answers")
async def put_answers(assessment_id: str, req: AnswersIn, access: TenantAccess = Depends(editor)):
    a = await _assessment_or_404(access, assessment_id)
    try:
        result = await submit_answers(access.repo, load_questionnaire(), a, req.answers, access.user_id)
    except AnswerError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except AssessmentClosed:
        raise HTTPException(status_code=409, detail="Assessment is completed; start a new assessment to change answers")
    logger.info("answers saved tenant=%s assessment=%s count=%d changed=%d",
                access.tenant_id, assessment_id, len(req.answers), result["changed_facts"])
    return {**result, **await _assessment_view(access, a)}


@router.get("/api/tenants/{tenant_id}/assessments/{assessment_id}/next")
async def get_next(assessment_id: str, access: TenantAccess = Depends(viewer)):
    await _assessment_or_404(access, assessment_id)
    qn = load_questionnaire()
    answers = await access.repo.get_answers(assessment_id)
    return {"next_question": _public_q(next_question(qn, answers)), "progress": progress(qn, answers)}


@router.post("/api/tenants/{tenant_id}/assessments/{assessment_id}/complete")
async def complete_assessment(assessment_id: str, access: TenantAccess = Depends(editor)):
    a = await _assessment_or_404(access, assessment_id)
    if a["status"] == "completed":
        return await _assessment_view(access, a)
    p = progress(load_questionnaire(), await access.repo.get_answers(assessment_id))
    if not p["complete"]:
        raise HTTPException(status_code=422, detail={"message": "Required questions unanswered",
                                                     "missing_required": p["missing_required"]})
    await access.repo.complete_assessment(assessment_id)
    return await _assessment_view(access, await access.repo.get_assessment(assessment_id))


# ── Opportunities & plan ─────────────────────────────────────────────────────

async def _brain_values(access: TenantAccess) -> dict:
    return brain_answers(await access.repo.list_facts())


@router.post("/api/tenants/{tenant_id}/assessments/{assessment_id}/opportunities")
async def generate_opportunities(assessment_id: str, access: TenantAccess = Depends(editor)):
    await _assessment_or_404(access, assessment_id)
    result = analyse(load_questionnaire(), await _brain_values(access))
    generation = await access.repo.save_opportunities(assessment_id, result["opportunities"])
    for role in {o["recommended_agent"]["agent_role"] for o in result["opportunities"]}:
        if not await access.repo.get_assignment(role):
            await access.repo.upsert_assignment(role, access.user_id, status="recommended")
    logger.info("opportunities generated tenant=%s assessment=%s gen=%d count=%d",
                access.tenant_id, assessment_id, generation, len(result["opportunities"]))
    return {"generation": generation, **result}


@router.get("/api/tenants/{tenant_id}/assessments/{assessment_id}/opportunities")
async def get_opportunities(assessment_id: str, access: TenantAccess = Depends(viewer)):
    await _assessment_or_404(access, assessment_id)
    generation, opps = await access.repo.latest_opportunities(assessment_id)
    if not generation:
        raise HTTPException(status_code=404, detail="No opportunity analysis yet")
    return {"generation": generation, "opportunities": opps}


@router.post("/api/tenants/{tenant_id}/assessments/{assessment_id}/plan", status_code=201)
async def generate_plan(assessment_id: str, access: TenantAccess = Depends(editor)):
    await _assessment_or_404(access, assessment_id)
    qn = load_questionnaire()
    values = await _brain_values(access)
    analysis = analyse(qn, values)
    content = build_plan(qn, values, analysis)
    company = values.get("exec.company_name") or (await access.repo.get_tenant())["name"]
    plan = await access.repo.save_plan(assessment_id, content, render_markdown(content, company), access.user_id)
    logger.info("plan generated tenant=%s assessment=%s plan=%s v=%d",
                access.tenant_id, assessment_id, plan["id"], plan["version"])
    return plan


@router.get("/api/tenants/{tenant_id}/plans/{plan_id}")
async def get_plan(plan_id: str, access: TenantAccess = Depends(viewer)):
    plan = await access.repo.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


# ── Brain facts, feedback, context ───────────────────────────────────────────

@router.get("/api/tenants/{tenant_id}/brain/facts")
async def list_facts(category: str | None = None, domain: str | None = None,
                     access: TenantAccess = Depends(viewer)):
    return await access.repo.list_facts(category=category, domain=domain)


@router.post("/api/tenants/{tenant_id}/brain/facts", status_code=201)
async def add_fact(req: FactIn, access: TenantAccess = Depends(editor)):
    if req.category not in FACT_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"category must be one of {FACT_CATEGORIES}")
    if req.domain not in _known_domains():
        raise HTTPException(status_code=422, detail="unknown domain")
    if req.sensitivity not in SENSITIVITY_LEVELS:
        raise HTTPException(status_code=422, detail=f"sensitivity must be one of {SENSITIVITY_LEVELS}")
    if len(json.dumps(req.value, ensure_ascii=False)) > MAX_FACT_CHARS:
        raise HTTPException(status_code=413, detail=f"fact value larger than {MAX_FACT_CHARS} characters")
    fact, _ = await access.repo.upsert_fact(
        fact_key=f"manual:{req.key}", category=req.category, domain=req.domain, value=req.value,
        sensitivity=req.sensitivity, source_type="manual", source_ref=f"user:{access.user_id}",
        created_by=access.user_id,
    )
    return fact


@router.get("/api/tenants/{tenant_id}/brain/facts/{fact_id}/history")
async def fact_history(fact_id: str, access: TenantAccess = Depends(viewer)):
    history = await access.repo.fact_history(fact_id)
    if not history:
        raise HTTPException(status_code=404, detail="Fact not found")
    return history


@router.get("/api/tenants/{tenant_id}/brain/feedback")
async def list_feedback(status: str | None = None, access: TenantAccess = Depends(viewer)):
    return await access.repo.list_feedback(status)


@router.post("/api/tenants/{tenant_id}/brain/feedback", status_code=201)
async def submit_feedback(req: FeedbackIn, access: TenantAccess = Depends(editor)):
    fact = await access.repo.get_fact(req.fact_id)
    if not fact or fact["status"] != "active":
        raise HTTPException(status_code=404, detail="Active fact not found")
    if req.kind == "correction" and req.proposed_value is None:
        raise HTTPException(status_code=422, detail="A correction needs proposed_value")
    return await access.repo.create_feedback(
        fact_id=req.fact_id, kind=req.kind, proposed_value=req.proposed_value,
        note=req.note, submitted_by=access.user_id,
    )


@router.post("/api/tenants/{tenant_id}/brain/feedback/{feedback_id}/resolve")
async def resolve_feedback(feedback_id: str, req: FeedbackResolve, access: TenantAccess = Depends(owner)):
    fb = await access.repo.get_feedback(feedback_id)
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found")
    if fb["status"] != "pending":
        raise HTTPException(status_code=409, detail="Feedback already resolved")
    result = {"feedback_id": feedback_id, "decision": req.decision, "new_fact": None}
    if req.decision == "accept" and fb["kind"] == "correction":
        fact = await access.repo.get_fact(fb["fact_id"])
        if not fact or fact["status"] != "active":
            raise HTTPException(status_code=409, detail="The fact changed since this feedback was submitted")
        new_value = fb["proposed_value"]
        if isinstance(fact["value"], dict) and "answer" in fact["value"] and not isinstance(new_value, dict):
            new_value = {**fact["value"], "answer": new_value}
        new_fact, _ = await access.repo.upsert_fact(
            fact_key=fact["fact_key"], category=fact["category"], domain=fact["domain"], value=new_value,
            sensitivity=fact["sensitivity"], source_type="correction", source_ref=f"feedback:{feedback_id}",
            created_by=access.user_id,
        )
        result["new_fact"] = new_fact
    await access.repo.mark_feedback(feedback_id, "accepted" if req.decision == "accept" else "rejected", access.user_id)
    logger.info("feedback resolved tenant=%s feedback=%s decision=%s", access.tenant_id, feedback_id, req.decision)
    return result


@router.get("/api/tenants/{tenant_id}/brain/context")
async def agent_context(agent_role: str, access: TenantAccess = Depends(viewer)):
    return await get_agent_context(access.repo, agent_role)


@router.get("/api/tenants/{tenant_id}/agents")
async def list_agent_assignments(access: TenantAccess = Depends(viewer)):
    return await access.repo.list_assignments()


@router.put("/api/tenants/{tenant_id}/agents/{agent_role}/scope")
async def set_agent_scope(agent_role: str, req: ScopeIn, access: TenantAccess = Depends(owner)):
    try:
        scope = validate_scope(req.model_dump(), _known_domains())
    except ScopeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    a = await access.repo.upsert_assignment(agent_role, access.user_id, context_scope=scope, set_scope=True)
    logger.info("agent scope set tenant=%s agent=%s", access.tenant_id, agent_role)
    return a
