"""Instagram Growth Agent — the 7 workflow step tools.

Each tool is called by the parent `instagram` agent. The handler is the
deterministic orchestrator for its step:

  1. validate the content plan exists
  2. enforce dependency guards (the workflow DAG lives here, not in a prompt)
  3. read upstream artifacts and inject them into the sub-agent prompt
  4. spawn the step's sub-agent (wrapped — a sub-agent failure becomes a clean
     tool error, it never crashes the parent's tool loop)
  5. save the result as a plan artifact
  6. return the full result to the parent

run_automation_setup is a guarded stub: live publishing arrives in Phases 3-4.
"""

import logging

from agents.base import BaseAgent
from agents.instagram_subagents import (
    NICHE_FINDER, VIRAL_BLUEPRINT, CAPTION_GENERATOR,
    HASHTAG_FORMULA, CONTENT_SCHEDULE, MONETIZATION_MAP,
)
from tools.instagram_accounts import get_account_summary
from tools.instagram_publish import list_scheduled_posts
from tools.plan_artifacts import get_content_plan, read_plan_artifact, save_plan_artifact
from tools.registry import ToolDef, registry

logger = logging.getLogger("core8.instagram")

_NO_NICHE = (
    "No niche chosen yet. Run run_niche_finder, then record the user's choice "
    "with update_content_plan(plan_id, niche=\"...\")."
)


async def _run_subagent(config, user_message: str) -> tuple[str | None, str | None]:
    """Run a step sub-agent. Returns (text, error) — exactly one is non-None."""
    try:
        text, _ = await BaseAgent(config).run(
            [{"role": "user", "content": user_message}]
        )
    except Exception as e:  # API error, timeout, etc. — never crash the parent
        logger.error("Instagram sub-agent %s failed: %s", config.id, e)
        return None, f"The {config.name} sub-agent failed: {e}"
    if not text or not text.strip():
        return None, f"The {config.name} sub-agent returned no content."
    return text, None


async def _require_plan(plan_id: str) -> tuple[dict | None, dict | None]:
    """Returns (plan, error). Exactly one is non-None."""
    plan = await get_content_plan(plan_id)
    if "error" in plan:
        return None, {"error": plan["error"]}
    return plan, None


async def _finish(plan_id: str, step: str, text: str, **extra) -> dict:
    """Save the step artifact and build the tool result."""
    saved = await save_plan_artifact(plan_id, step, text)
    if "error" in saved:
        return {"error": saved["error"]}
    return {"step": step, "plan_id": plan_id, "result": text, **extra}


# ── Step 1 — Niche Finder ───────────────────────────────────────────────────

async def run_niche_finder(plan_id: str, brief: str = "") -> dict:
    plan, err = await _require_plan(plan_id)
    if err:
        return err
    user_msg = (
        f"Founder brief: {brief.strip() or '(none provided — give broadly viable niches)'}\n\n"
        "Produce the 10-niche analysis."
    )
    text, sub_err = await _run_subagent(NICHE_FINDER, user_msg)
    if sub_err:
        return {"error": sub_err}
    return await _finish(
        plan_id, "niche", text,
        next="Present these niches to the user, then record their pick with "
             "update_content_plan(plan_id, niche=\"...\").",
    )


# ── Step 2 — Viral Content Blueprint ────────────────────────────────────────

async def run_viral_blueprint(plan_id: str) -> dict:
    plan, err = await _require_plan(plan_id)
    if err:
        return err
    niche = (plan.get("niche") or "").strip()
    if not niche:
        return {"error": "no_niche", "message": _NO_NICHE}
    user_msg = f"Chosen niche: {niche}\n\nProduce 20 viral content ideas for this niche."
    text, sub_err = await _run_subagent(VIRAL_BLUEPRINT, user_msg)
    if sub_err:
        return {"error": sub_err}
    return await _finish(plan_id, "viral", text)


# ── Step 3 — Caption Generator ──────────────────────────────────────────────

async def run_caption_generator(plan_id: str, content_idea: str = "") -> dict:
    plan, err = await _require_plan(plan_id)
    if err:
        return err
    if not content_idea.strip():
        return {
            "error": "missing_idea",
            "message": "content_idea is required. Pick one idea from the viral "
                       "blueprint and pass it as content_idea.",
        }
    user_msg = f"Content idea: {content_idea.strip()}\n\nWrite the caption."
    text, sub_err = await _run_subagent(CAPTION_GENERATOR, user_msg)
    if sub_err:
        return {"error": sub_err}
    return await _finish(plan_id, "caption", text)


# ── Step 4 — Hashtag & Hook Formula ─────────────────────────────────────────

async def run_hashtag_formula(plan_id: str) -> dict:
    plan, err = await _require_plan(plan_id)
    if err:
        return err
    niche = (plan.get("niche") or "").strip()
    if not niche:
        return {"error": "no_niche", "message": _NO_NICHE}
    user_msg = f"Niche: {niche}\n\nProduce the 15 hashtags and 5 hooks."
    text, sub_err = await _run_subagent(HASHTAG_FORMULA, user_msg)
    if sub_err:
        return {"error": sub_err}
    return await _finish(plan_id, "hashtag", text)


# ── Step 5 — Content Schedule ───────────────────────────────────────────────

async def run_content_schedule(plan_id: str) -> dict:
    plan, err = await _require_plan(plan_id)
    if err:
        return err
    niche = (plan.get("niche") or "").strip()
    if not niche:
        return {"error": "no_niche", "message": _NO_NICHE}
    viral = await read_plan_artifact(plan_id, "viral")
    if not viral.get("exists"):
        return {
            "error": "no_viral",
            "message": "No viral content ideas yet. Run run_viral_blueprint before "
                       "building the schedule.",
        }
    user_msg = (
        f"Niche: {niche}\n\n"
        f"Viral content ideas to draw from:\n{viral['content']}\n\n"
        "Build the 30-day content calendar."
    )
    text, sub_err = await _run_subagent(CONTENT_SCHEDULE, user_msg)
    if sub_err:
        return {"error": sub_err}
    return await _finish(plan_id, "schedule", text)


# ── Step 6 — Monetization Map ───────────────────────────────────────────────

async def run_monetization_map(plan_id: str) -> dict:
    plan, err = await _require_plan(plan_id)
    if err:
        return err
    niche = (plan.get("niche") or "").strip()
    if not niche:
        return {"error": "no_niche", "message": _NO_NICHE}
    user_msg = f"Niche: {niche}\n\nMap 5 monetization paths for this niche."
    text, sub_err = await _run_subagent(MONETIZATION_MAP, user_msg)
    if sub_err:
        return {"error": sub_err}
    return await _finish(plan_id, "monetize", text)


# ── Step 7 — Automation Setup (guarded stub — see Phases 3-4) ────────────────

async def run_automation_setup(plan_id: str) -> dict:
    plan, err = await _require_plan(plan_id)
    if err:
        return err
    schedule = await read_plan_artifact(plan_id, "schedule")
    if not schedule.get("exists"):
        return {
            "error": "no_schedule",
            "message": "No content schedule yet. Run run_content_schedule before "
                       "setting up automation.",
        }
    account = await get_account_summary()
    if account is None:
        return {
            "error": "no_account",
            "message": "No Instagram account is connected. Use connect_instagram "
                       "before setting up automated publishing.",
        }
    queued = await list_scheduled_posts()
    plan_posts = [p for p in queued if p.get("plan_id") == plan_id]
    pending = sum(1 for p in plan_posts if p["status"] == "pending")
    return {
        "step": "automation_setup",
        "plan_id": plan_id,
        "account": account["username"],
        "queued_for_plan": len(plan_posts),
        "pending": pending,
        "message": (
            f"Automation is ready — connected as @{account['username']} and the "
            f"30-day schedule exists. {pending} post(s) currently queued for this "
            "plan. To schedule a post, call queue_post with its media_url (a public "
            "image or video URL), caption, post_type, and scheduled_for (UTC). The "
            "publishing scheduler then posts each one automatically at its time."
        ),
    }


# ── Registration ────────────────────────────────────────────────────────────

def register_instagram_step_tools():
    registry.register(ToolDef(
        name="run_niche_finder",
        description="Step 1. Find 10 viable Instagram theme-page niches. Optionally "
                    "pass a brief describing the user's interests and goals.",
        input_schema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string", "description": "Content plan id from create_content_plan"},
                "brief":   {"type": "string", "description": "The user's interests / goals (optional)"},
            },
            "required": ["plan_id"],
        },
        handler=run_niche_finder,
    ))
    registry.register(ToolDef(
        name="run_viral_blueprint",
        description="Step 2. Generate 20 viral content ideas for the plan's chosen "
                    "niche. Requires a niche recorded via update_content_plan.",
        input_schema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
            },
            "required": ["plan_id"],
        },
        handler=run_viral_blueprint,
    ))
    registry.register(ToolDef(
        name="run_caption_generator",
        description="Step 3. Write a viral-style caption for one specific content "
                    "idea. Pass the idea (from the viral blueprint) as content_idea.",
        input_schema={
            "type": "object",
            "properties": {
                "plan_id":      {"type": "string"},
                "content_idea": {"type": "string", "description": "The content idea to caption"},
            },
            "required": ["plan_id", "content_idea"],
        },
        handler=run_caption_generator,
    ))
    registry.register(ToolDef(
        name="run_hashtag_formula",
        description="Step 4. Generate 15 hashtags and 5 hooks for the plan's chosen "
                    "niche. Requires a niche recorded via update_content_plan.",
        input_schema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
            },
            "required": ["plan_id"],
        },
        handler=run_hashtag_formula,
    ))
    registry.register(ToolDef(
        name="run_content_schedule",
        description="Step 5. Build a 30-day content calendar. Requires a chosen "
                    "niche and the viral blueprint (run_viral_blueprint) first.",
        input_schema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
            },
            "required": ["plan_id"],
        },
        handler=run_content_schedule,
    ))
    registry.register(ToolDef(
        name="run_monetization_map",
        description="Step 6. Map 5 ways to monetize the page for the plan's chosen "
                    "niche. Requires a niche recorded via update_content_plan.",
        input_schema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
            },
            "required": ["plan_id"],
        },
        handler=run_monetization_map,
    ))
    registry.register(ToolDef(
        name="run_automation_setup",
        description="Step 7. Check automated-publishing readiness — verifies the "
                    "content schedule and a connected Instagram account, and "
                    "reports the queue. Use queue_post to schedule individual posts.",
        input_schema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
            },
            "required": ["plan_id"],
        },
        handler=run_automation_setup,
    ))
