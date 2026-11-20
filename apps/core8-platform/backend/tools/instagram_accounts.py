"""Instagram account storage — one connected account per tenant (ig_accounts).

Each tenant connects at most ONE Instagram Business account, stored in a row whose
id is the tenant_id (CORE8-005). The access token is Fernet-encrypted at rest and
decrypted only transiently when a Graph API call needs it.

The connect_instagram / list_ig_accounts registry tools are added in
register_instagram_account_tools().
"""

import aiosqlite

from database import get_db
from tenancy import current_tenant
from security.token_crypto import encrypt_token, decrypt_token
from tools import instagram_api
from tools.instagram_api import build_oauth_url, GraphAPIError
from tools.registry import ToolDef, registry

async def save_ig_account(ig_user_id: str, fb_page_id: str, username: str,
                          access_token: str, token_expires_at: str | None) -> dict:
    """Upsert the current tenant's connected account. Encrypts the token before storing."""
    enc = encrypt_token(access_token)
    tenant_id = current_tenant()
    async with get_db() as db:
        await db.execute(
            """INSERT INTO ig_accounts
                   (id, tenant_id, ig_user_id, fb_page_id, username, access_token, token_expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 ig_user_id=excluded.ig_user_id,
                 fb_page_id=excluded.fb_page_id,
                 username=excluded.username,
                 access_token=excluded.access_token,
                 token_expires_at=excluded.token_expires_at,
                 updated_at=datetime('now')""",
            (tenant_id, tenant_id, ig_user_id, fb_page_id, username, enc, token_expires_at),
        )
        await db.commit()
    return {"ig_user_id": ig_user_id, "username": username, "fb_page_id": fb_page_id}


async def list_accounts_for_refresh() -> list[dict]:
    """All tenants' accounts (tenant_id + expiry only, no tokens) for the token refresher.
    A deliberately cross-tenant read; never exposed as a tool."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT tenant_id, token_expires_at FROM ig_accounts") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_ig_account() -> dict | None:
    """Internal use — the connected account WITH its decrypted access token.
    Returns None if no account is connected."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM ig_accounts WHERE tenant_id=? AND id=?", (current_tenant(), current_tenant()),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    acct = dict(row)
    acct["access_token"] = decrypt_token(acct["access_token"])
    return acct


async def get_account_summary() -> dict | None:
    """Public-safe — connected account info with NO access token. None if unconnected."""
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT ig_user_id, username, fb_page_id, token_expires_at, connected_at
               FROM ig_accounts WHERE tenant_id=? AND id=?""",
            (current_tenant(), current_tenant()),
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


# ── Registry tools ──────────────────────────────────────────────────────────

async def connect_instagram() -> dict:
    """Build the Meta OAuth consent URL the user opens to connect their account."""
    try:
        url = build_oauth_url(current_tenant())
    except GraphAPIError as e:
        return {
            "error": str(e),
            "message": "Instagram is not configured yet — the operator must set "
                       "META_APP_ID and META_APP_SECRET in the backend .env.",
        }
    return {
        "connect_url": url,
        "message": "Give this link to the user. Opening it and approving grants "
                   "Core8-AI access to their Instagram Business account; the "
                   "connection then completes automatically.",
    }


async def list_ig_accounts() -> dict:
    """Show the currently connected Instagram account (never the access token)."""
    summary = await get_account_summary()
    if summary is None:
        return {
            "connected": False,
            "message": "No Instagram account is connected. Use connect_instagram.",
        }
    return {"connected": True, "account": summary}


async def get_account_insights(period_days: int = 7) -> dict:
    """Reach, engagement, follower count, and a publishing summary for the
    connected account. Period defaults to the last 7 days."""
    acct = await _get_account_with_token()
    if acct is None:
        return {"error": "No Instagram account is connected. Use connect_instagram first."}
    try:
        profile = await instagram_api.fetch_account_profile(
            acct["ig_user_id"], acct["access_token"])
        raw = await instagram_api.fetch_account_insights(
            acct["ig_user_id"], acct["access_token"], period_days)
    except GraphAPIError as e:
        return {"error": f"Failed to fetch insights: {e}"}
    metrics = {m.get("name"): (m.get("total_value", {}) or {}).get("value", 0)
               for m in raw.get("data", [])}
    # Local publishing summary (no Graph calls)
    from tools.instagram_publish import list_scheduled_posts, count_published_last_24h
    pending = await list_scheduled_posts(status="pending", limit=500)
    published = await list_scheduled_posts(status="published", limit=500)
    return {
        "account": {
            "username": profile.get("username"),
            "followers_count": profile.get("followers_count"),
            "media_count": profile.get("media_count"),
        },
        "insights": {
            "period_days": period_days,
            "reach": metrics.get("reach", 0),
            "accounts_engaged": metrics.get("accounts_engaged", 0),
            "total_interactions": metrics.get("total_interactions", 0),
            "profile_views": metrics.get("profile_views", 0),
        },
        "publishing": {
            "queued_pending": len(pending),
            "total_published": len(published),
            "published_last_24h": await count_published_last_24h(),
        },
    }


async def _get_account_with_token() -> dict | None:
    """Convenience wrapper — same as get_ig_account; named for readability."""
    return await get_ig_account()


async def get_post_insights(ig_media_id: str) -> dict:
    """Per-post Instagram metrics: reach, likes, comments, saves, shares,
    total interactions. ig_media_id is the value returned by publish."""
    if not ig_media_id or not ig_media_id.strip():
        return {"error": "ig_media_id is required."}
    acct = await _get_account_with_token()
    if acct is None:
        return {"error": "No Instagram account is connected. Use connect_instagram first."}
    try:
        raw = await instagram_api.fetch_post_insights(
            ig_media_id.strip(), acct["access_token"])
    except GraphAPIError as e:
        return {"error": f"Failed to fetch post insights: {e}"}
    metrics: dict[str, int] = {}
    for m in raw.get("data", []):
        values = m.get("values", []) or []
        metrics[m.get("name")] = values[0].get("value", 0) if values else 0
    return {"ig_media_id": ig_media_id.strip(), "metrics": metrics}


def register_instagram_account_tools():
    registry.register(ToolDef(
        name="connect_instagram",
        description=(
            "Start connecting an Instagram Business account. Returns a URL the "
            "user opens to grant access; the connection finishes automatically "
            "once they approve."
        ),
        input_schema={"type": "object", "properties": {}},
        handler=connect_instagram,
    ))
    registry.register(ToolDef(
        name="list_ig_accounts",
        description=(
            "Show the Instagram account currently connected to Core8-AI — "
            "username, ids, token expiry — or report that none is connected."
        ),
        input_schema={"type": "object", "properties": {}},
        handler=list_ig_accounts,
    ))
    registry.register(ToolDef(
        name="get_account_insights",
        description=(
            "Live performance metrics for the connected Instagram account — "
            "reach, accounts engaged, total interactions, profile views — over "
            "the last N days (default 7), plus current follower count and a "
            "publishing summary from the queue."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "period_days": {"type": "integer", "description": "Look-back window in days (default 7)"},
            },
        },
        handler=get_account_insights,
    ))
    registry.register(ToolDef(
        name="get_post_insights",
        description=(
            "Lifetime metrics for one published Instagram post — reach, likes, "
            "comments, saves, shares, total interactions. Pass the ig_media_id "
            "(returned after publish; visible in list_scheduled_posts)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "ig_media_id": {"type": "string", "description": "Instagram media id of the published post"},
            },
            "required": ["ig_media_id"],
        },
        handler=get_post_insights,
    ))
