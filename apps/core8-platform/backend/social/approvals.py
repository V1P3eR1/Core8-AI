"""Approval records bound to the exact publication payload.

binding_hash = sha256(account_id | format | caption_hash | assets_hash | scheduled_for | settings_hash)

If any publication-relevant field of the content item changes after approval,
`check_item_approval` reports a mismatch and `invalidate_if_changed` marks the
approval invalidated (and the item goes back to needs_review). This is code,
not prompt — the LLM cannot bypass it.
"""

from .db import audit, execute, fetch_all, fetch_one, jdump, jload, new_id, sha256_text, utc_str
from .media import get_asset


async def compute_binding(item: dict) -> dict:
    """Hashes for the item's current publication-relevant state."""
    asset_ids = jload(item.get("asset_ids"), []) or []
    shas = []
    for aid in asset_ids:
        a = await get_asset(aid)
        shas.append(a["sha256"] if a else f"missing:{aid}")
    cover = item.get("cover_asset_id") or ""
    if cover:
        ca = await get_asset(cover)
        shas.append("cover:" + (ca["sha256"] if ca else f"missing:{cover}"))
    pkg = jload(item.get("package"), {}) or {}
    settings_relevant = {
        "alt_text": pkg.get("alt_text", ""),
        "share_to_feed": pkg.get("share_to_feed", True),
        "is_ai_generated": pkg.get("is_ai_generated", False),
        "location_id": pkg.get("location_id"),
        "collaborators": pkg.get("collaborators", []),
    }
    caption_hash = sha256_text(item.get("caption") or "")
    assets_hash = sha256_text("|".join(shas))
    settings_hash = sha256_text(jdump(settings_relevant))
    account_id = item.get("account_id") or ""
    scheduled_for = item.get("scheduled_for") or ""
    binding = sha256_text("|".join([account_id, item["format"], caption_hash, assets_hash,
                                    scheduled_for, settings_hash]))
    return {"account_id": account_id, "format": item["format"], "caption_hash": caption_hash,
            "assets_hash": assets_hash, "scheduled_for": scheduled_for or None,
            "settings_hash": settings_hash, "binding_hash": binding}


async def active_approval(item_id: str) -> dict | None:
    return await fetch_one(
        "SELECT * FROM sm_approvals WHERE content_item_id=? AND status='active' "
        "ORDER BY approved_at DESC LIMIT 1", (item_id,))


async def create_approval(item: dict, approved_by: str) -> dict:
    """Approve the item exactly as it is now. Previous active approvals are consumed."""
    b = await compute_binding(item)
    if not b["account_id"]:
        raise ValueError("לא ניתן לאשר ללא חשבון יעד (account_id)")
    await execute("UPDATE sm_approvals SET status='invalidated', invalidated_reason='superseded', "
                  "invalidated_at=? WHERE content_item_id=? AND status='active'",
                  (utc_str(), item["id"]))
    approval_id = new_id()
    await execute(
        """INSERT INTO sm_approvals (id, content_item_id, account_id, format, caption_hash, assets_hash,
             scheduled_for, settings_hash, binding_hash, approved_by)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (approval_id, item["id"], b["account_id"], b["format"], b["caption_hash"], b["assets_hash"],
         b["scheduled_for"], b["settings_hash"], b["binding_hash"], approved_by))
    await audit(approved_by, "approve", "content_item", item["id"], {"binding": b["binding_hash"]})
    return await fetch_one("SELECT * FROM sm_approvals WHERE id=?", (approval_id,))


async def check_item_approval(item: dict) -> dict:
    """{valid: bool, approval: row|None, reason: str, binding: dict}"""
    b = await compute_binding(item)
    ap = await active_approval(item["id"])
    if not ap:
        return {"valid": False, "approval": None, "reason": "no_active_approval", "binding": b}
    if ap["binding_hash"] != b["binding_hash"]:
        changed = [k for k in ("account_id", "format", "caption_hash", "assets_hash",
                               "scheduled_for", "settings_hash") if (ap[k] or "") != (b[k] or "")]
        return {"valid": False, "approval": ap, "reason": "changed:" + ",".join(changed), "binding": b}
    return {"valid": True, "approval": ap, "reason": "ok", "binding": b}


async def invalidate_if_changed(item: dict, actor: str = "system") -> dict | None:
    """Called after any edit. Invalidates a stale approval and returns it."""
    res = await check_item_approval(item)
    if res["approval"] and not res["valid"]:
        await execute("UPDATE sm_approvals SET status='invalidated', invalidated_reason=?, invalidated_at=? "
                      "WHERE id=?", (res["reason"], utc_str(), res["approval"]["id"]))
        await audit(actor, "approval_invalidated", "content_item", item["id"], {"reason": res["reason"]})
        return res["approval"]
    return None


async def list_approvals(item_id: str | None = None) -> list[dict]:
    if item_id:
        return await fetch_all("SELECT * FROM sm_approvals WHERE content_item_id=? ORDER BY approved_at DESC",
                               (item_id,))
    return await fetch_all("SELECT * FROM sm_approvals ORDER BY approved_at DESC LIMIT 200")
