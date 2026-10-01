"""Content-plan tools — shared planning storage for the Instagram Growth Agent.

A content_plan is the spine of one Instagram workflow run. plan_artifacts holds
the per-step output (niche research, viral ideas, captions, hashtags, calendar,
monetization). Step sub-agents read upstream artifacts and write their own
through these tools, so each step builds on the last.
"""

import uuid
import aiosqlite
from database import get_db
from tools.registry import ToolDef, registry

_VALID_STATUSES = {"planning", "scheduled", "active"}
_VALID_STEPS = {"niche", "viral", "caption", "hashtag", "schedule", "monetize"}


async def _plan_exists(db, plan_id: str) -> bool:
    async with db.execute("SELECT 1 FROM content_plans WHERE id=?", (plan_id,)) as cur:
        return await cur.fetchone() is not None


async def create_content_plan(niche: str = "") -> dict:
    plan_id = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            "INSERT INTO content_plans (id, niche) VALUES (?, ?)",
            (plan_id, niche),
        )
        await db.commit()
    return {"id": plan_id, "niche": niche, "status": "planning"}


async def list_content_plans(limit: int = 50) -> list[dict]:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT p.id, p.niche, p.status, p.created_at, p.updated_at,
                      COUNT(a.id) AS artifact_count
               FROM content_plans p
               LEFT JOIN plan_artifacts a ON a.plan_id = p.id
               GROUP BY p.id
               ORDER BY p.updated_at DESC
               LIMIT ?""",
            (min(limit, 200),),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_content_plan(plan_id: str) -> dict:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM content_plans WHERE id=?", (plan_id,)
        ) as cur:
            plan = await cur.fetchone()
        if not plan:
            return {"error": f"Content plan {plan_id} not found"}
        async with db.execute(
            """SELECT step, length(content) AS size_bytes, updated_at
               FROM plan_artifacts WHERE plan_id=? ORDER BY created_at""",
            (plan_id,),
        ) as cur:
            artifacts = await cur.fetchall()
    result = dict(plan)
    result["artifacts"] = [dict(a) for a in artifacts]
    return result


async def update_content_plan(plan_id: str, niche: str = "", status: str = "") -> dict:
    updates, params = [], []
    if niche:
        updates.append("niche=?")
        params.append(niche)
    if status:
        if status not in _VALID_STATUSES:
            return {"error": f"Invalid status '{status}'. Valid: {sorted(_VALID_STATUSES)}"}
        updates.append("status=?")
        params.append(status)
    if not updates:
        return {"error": "No fields to update (provide niche and/or status)"}
    updates.append("updated_at=datetime('now')")
    params.append(plan_id)
    async with get_db() as db:
        if not await _plan_exists(db, plan_id):
            return {"error": f"Content plan {plan_id} not found"}
        await db.execute(
            f"UPDATE content_plans SET {', '.join(updates)} WHERE id=?", params
        )
        await db.commit()
    return {"updated": plan_id}


async def save_plan_artifact(plan_id: str, step: str, content: str) -> dict:
    if step not in _VALID_STEPS:
        return {"error": f"Invalid step '{step}'. Valid: {sorted(_VALID_STEPS)}"}
    if not content.strip():
        return {"error": "content is empty"}
    async with get_db() as db:
        if not await _plan_exists(db, plan_id):
            return {"error": f"Content plan {plan_id} not found — call create_content_plan first"}
        await db.execute(
            """INSERT INTO plan_artifacts (id, plan_id, step, content)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(plan_id, step) DO UPDATE SET
                 content=excluded.content,
                 updated_at=datetime('now')""",
            (str(uuid.uuid4()), plan_id, step, content),
        )
        await db.execute(
            "UPDATE content_plans SET updated_at=datetime('now') WHERE id=?", (plan_id,)
        )
        await db.commit()
    return {"saved": f"{plan_id}/{step}", "bytes": len(content)}


async def read_plan_artifact(plan_id: str, step: str) -> dict:
    if step not in _VALID_STEPS:
        return {"error": f"Invalid step '{step}'. Valid: {sorted(_VALID_STEPS)}"}
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT content, updated_at FROM plan_artifacts WHERE plan_id=? AND step=?",
            (plan_id, step),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"No '{step}' artifact for plan {plan_id}", "exists": False}
    return {
        "plan_id": plan_id,
        "step": step,
        "content": row["content"],
        "updated_at": row["updated_at"],
        "exists": True,
    }


def register_plan_artifact_tools():
    registry.register(ToolDef(
        name="create_content_plan",
        description=(
            "Start a new Instagram content plan. Returns a plan_id that every "
            "workflow step uses. Create one plan per Instagram page / workflow run."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "niche": {"type": "string", "description": "Chosen niche, if already known (optional)"},
            },
        },
        handler=create_content_plan,
    ))
    registry.register(ToolDef(
        name="list_content_plans",
        description="List Instagram content plans with status and artifact counts, most recently updated first.",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results (default 50)"},
            },
        },
        handler=list_content_plans,
    ))
    registry.register(ToolDef(
        name="get_content_plan",
        description="Get one content plan: niche, status, and which workflow steps already have a saved artifact.",
        input_schema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
            },
            "required": ["plan_id"],
        },
        handler=get_content_plan,
    ))
    registry.register(ToolDef(
        name="update_content_plan",
        description="Update a content plan — record the chosen niche or advance status (planning|scheduled|active).",
        input_schema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
                "niche":   {"type": "string", "description": "Chosen niche"},
                "status":  {"type": "string", "description": "planning|scheduled|active"},
            },
            "required": ["plan_id"],
        },
        handler=update_content_plan,
    ))
    registry.register(ToolDef(
        name="save_plan_artifact",
        description=(
            "Save the output of a workflow step to a content plan. step is one of: "
            "niche, viral, caption, hashtag, schedule, monetize. Re-saving the same "
            "step overwrites the previous artifact."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
                "step":    {"type": "string", "description": "niche|viral|caption|hashtag|schedule|monetize"},
                "content": {"type": "string", "description": "The step output (markdown or JSON)"},
            },
            "required": ["plan_id", "step", "content"],
        },
        handler=save_plan_artifact,
    ))
    registry.register(ToolDef(
        name="read_plan_artifact",
        description=(
            "Read a workflow step's saved artifact from a content plan. "
            "step: niche|viral|caption|hashtag|schedule|monetize. "
            "The 'exists' field tells you whether the artifact was found."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
                "step":    {"type": "string"},
            },
            "required": ["plan_id", "step"],
        },
        handler=read_plan_artifact,
    ))
