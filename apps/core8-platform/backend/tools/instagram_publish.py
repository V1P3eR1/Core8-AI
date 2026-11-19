"""Scheduled-post storage and the publishing queue tools.

queue_post inserts a row into scheduled_posts; the scheduler (scheduler.py)
picks up due rows and publishes them. The claim/mark_* helpers are the
scheduler's data layer — they are not registry tools.

Times are stored and compared in UTC ('YYYY-MM-DD HH:MM:SS'), matching
SQLite's datetime('now').
"""

import datetime
import json
import uuid

import aiosqlite

from database import get_db
from tenancy import current_tenant
from tools.registry import ToolDef, registry

_VALID_POST_TYPES = {"image", "reel", "carousel"}


def _normalize_when(value: str) -> str | None:
    """Parse an ISO datetime/date to UTC 'YYYY-MM-DD HH:MM:SS'. None if invalid."""
    try:
        dt = datetime.datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse_media_urls(d: dict) -> dict:
    """JSON-parse the media_urls column on a row dict (in-place + return)."""
    raw = d.get("media_urls")
    if raw:
        try:
            d["media_urls"] = json.loads(raw)
        except (ValueError, TypeError):
            d["media_urls"] = None
    else:
        d["media_urls"] = None
    return d


# ── Queue tools (agent-facing) ──────────────────────────────────────────────

async def queue_post(scheduled_for: str, media_url: str = "",
                     media_urls: list[str] | None = None,
                     caption: str = "", post_type: str = "image",
                     plan_id: str = "") -> dict:
    if post_type not in _VALID_POST_TYPES:
        return {"error": f"Invalid post_type '{post_type}'. Valid: {sorted(_VALID_POST_TYPES)}"}
    when = _normalize_when(scheduled_for)
    if when is None:
        return {"error": f"scheduled_for '{scheduled_for}' is not a valid ISO datetime "
                         "(e.g. 2026-06-01T09:00:00). Times are UTC."}
    if post_type == "carousel":
        urls = media_urls or []
        if not isinstance(urls, list):
            return {"error": "media_urls must be a list of URLs for carousel posts."}
        urls = [u.strip() for u in urls if isinstance(u, str) and u.strip()]
        if not (2 <= len(urls) <= 10):
            return {"error": f"Carousel posts need 2-10 image URLs, got {len(urls)}."}
        primary_url = urls[0]
        media_urls_json: str | None = json.dumps(urls)
    else:
        if not media_url.strip():
            return {"error": "media_url is required — a public URL Instagram can fetch."}
        primary_url = media_url.strip()
        media_urls_json = None
    post_id = str(uuid.uuid4())
    tenant_id = current_tenant()
    async with get_db() as db:
        if plan_id:
            async with db.execute(
                "SELECT 1 FROM content_plans WHERE tenant_id=? AND id=?", (tenant_id, plan_id),
            ) as cur:
                if await cur.fetchone() is None:
                    return {"error": f"Content plan {plan_id} not found"}
        await db.execute(
            """INSERT INTO scheduled_posts
                   (tenant_id, id, plan_id, post_type, media_url, media_urls, caption, scheduled_for)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (tenant_id, post_id, plan_id or None, post_type, primary_url, media_urls_json,
             caption, when),
        )
        await db.commit()
    return {"id": post_id, "post_type": post_type, "scheduled_for": when,
            "status": "pending"}


async def list_scheduled_posts(status: str = "", limit: int = 50) -> list[dict]:
    cols = ("id, plan_id, post_type, media_url, media_urls, caption, scheduled_for, "
            "status, ig_media_id, attempts, last_error")
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        if status:
            query = (f"SELECT {cols} FROM scheduled_posts WHERE tenant_id=? AND status=? "
                     "ORDER BY scheduled_for LIMIT ?")
            args = (current_tenant(), status, min(limit, 200))
        else:
            query = (f"SELECT {cols} FROM scheduled_posts WHERE tenant_id=? "
                     "ORDER BY scheduled_for LIMIT ?")
            args = (current_tenant(), min(limit, 200))
        async with db.execute(query, args) as cur:
            rows = await cur.fetchall()
    return [_parse_media_urls(dict(r)) for r in rows]


async def cancel_scheduled_post(post_id: str) -> dict:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT status FROM scheduled_posts WHERE tenant_id=? AND id=?", (current_tenant(), post_id),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return {"error": f"Scheduled post {post_id} not found"}
        if row["status"] != "pending":
            return {"error": f"Cannot cancel — post is '{row['status']}', not 'pending'."}
        await db.execute(
            "UPDATE scheduled_posts SET status='cancelled', updated_at=datetime('now') "
            "WHERE tenant_id=? AND id=?", (current_tenant(), post_id),
        )
        await db.commit()
    return {"cancelled": post_id}


# ── Scheduler data layer (used by scheduler.py — not registry tools) ────────

async def claim_due_posts(limit: int = 10) -> list[dict]:
    """Pending posts whose scheduled_for (UTC) has passed, across ALL tenants.

    The only deliberately cross-tenant read: used by the scheduler, never exposed as a
    tool. Each row carries tenant_id; the scheduler publishes it inside use_tenant(...).
    media_urls is parsed from its JSON column."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM scheduled_posts
               WHERE status='pending' AND scheduled_for <= datetime('now')
               ORDER BY scheduled_for LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
    return [_parse_media_urls(dict(r)) for r in rows]


async def mark_publishing(post_id: str) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE scheduled_posts SET status='publishing', updated_at=datetime('now') "
            "WHERE tenant_id=? AND id=?", (current_tenant(), post_id),
        )
        await db.commit()


async def mark_published(post_id: str, ig_media_id: str) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE scheduled_posts SET status='published', ig_media_id=?, "
            "updated_at=datetime('now') WHERE tenant_id=? AND id=?",
            (ig_media_id, current_tenant(), post_id),
        )
        await db.commit()


async def mark_attempt_failed(post_id: str, error: str, give_up: bool) -> None:
    """Record a failed publish attempt. give_up -> 'failed'; otherwise back to
    'pending' so the scheduler retries it on a later tick."""
    async with get_db() as db:
        await db.execute(
            """UPDATE scheduled_posts
               SET status=?, attempts=attempts+1, last_error=?, updated_at=datetime('now')
               WHERE tenant_id=? AND id=?""",
            ("failed" if give_up else "pending", error[:500], current_tenant(), post_id),
        )
        await db.commit()


async def count_published_last_24h() -> int:
    """Posts this tenant published in the last 24h — backs the per-account API cap (25/day)."""
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) FROM scheduled_posts "
            "WHERE tenant_id=? AND status='published' AND updated_at >= datetime('now','-1 day')",
            (current_tenant(),),
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else 0


# ── Registration ────────────────────────────────────────────────────────────

def register_instagram_publish_tools():
    registry.register(ToolDef(
        name="queue_post",
        description=(
            "Schedule one Instagram post for automatic publishing. "
            "For image/reel posts: pass media_url (single public URL). "
            "For carousel posts: pass post_type='carousel' and media_urls "
            "(a list of 2-10 image URLs). scheduled_for is ISO datetime in UTC."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "scheduled_for": {"type": "string", "description": "ISO datetime, UTC (e.g. 2026-06-01T09:00:00)"},
                "media_url":     {"type": "string", "description": "Public URL of the image or video (image/reel)"},
                "media_urls":    {"type": "array", "items": {"type": "string"},
                                  "description": "List of 2-10 image URLs (carousel only)"},
                "caption":       {"type": "string", "description": "Post caption"},
                "post_type":     {"type": "string", "description": "image | reel | carousel (default image)"},
                "plan_id":       {"type": "string", "description": "Originating content plan id (optional)"},
            },
            "required": ["scheduled_for"],
        },
        handler=queue_post,
    ))
    registry.register(ToolDef(
        name="list_scheduled_posts",
        description="List queued/published Instagram posts, optionally filtered by "
                    "status (pending|publishing|published|failed|cancelled).",
        input_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status (optional)"},
                "limit":  {"type": "integer", "description": "Max results (default 50)"},
            },
        },
        handler=list_scheduled_posts,
    ))
    registry.register(ToolDef(
        name="cancel_scheduled_post",
        description="Cancel a pending scheduled post so it will not publish. "
                    "Only posts still in 'pending' status can be cancelled.",
        input_schema={
            "type": "object",
            "properties": {
                "post_id": {"type": "string"},
            },
            "required": ["post_id"],
        },
        handler=cancel_scheduled_post,
    ))
