"""Sources, ideas and content items — storage + the human-facing transitions.

Status flow for sm_content_items:
draft → needs_review → approved → scheduled → publishing → published
                      ↘ rejected            ↘ failed / needs_manual_review
Any edit after approval invalidates the approval and moves the item back to
needs_review (see approvals.py).
"""

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

from .approvals import invalidate_if_changed
from .db import audit, execute, fetch_all, fetch_one, jdump, jload, local_to_utc, new_id, utc_str
from .fact_check import check_item

ITEM_STATUSES = ("draft", "needs_review", "approved", "scheduled", "publishing", "published",
                 "failed", "needs_manual_review", "rejected", "paused")
PUBLICATION_FIELDS = ("caption", "asset_ids", "cover_asset_id", "scheduled_for", "account_id",
                      "format", "package")


# ── Sources ────────────────────────────────────────────────────────────────

def normalise_url(url: str) -> str:
    p = urlsplit(url.strip())
    query = "&".join(q for q in p.query.split("&")
                     if q and not q.lower().startswith(("utm_", "fbclid", "gclid", "ref=")))
    return urlunsplit((p.scheme.lower() or "https", p.netloc.lower(), p.path.rstrip("/") or "/", query, ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(normalise_url(url).encode()).hexdigest()


async def upsert_source(rec: dict) -> tuple[dict, bool]:
    """Insert unless a record with the same normalised URL exists. Returns (row, created)."""
    h = url_hash(rec["url"])
    existing = await fetch_one("SELECT * FROM sm_sources WHERE url_hash=?", (h,))
    if existing:
        return existing, False
    sid = new_id()
    await execute(
        """INSERT INTO sm_sources (id, title, url, url_hash, publisher, published_at, event_at, summary,
             relevance, unknowns, source_type, confidence, trend_verified, angle, topic, status, is_demo,
             provider, raw)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (sid, rec.get("title") or rec["url"], rec["url"], h, rec.get("publisher"), rec.get("published_at"),
         rec.get("event_at"), rec.get("summary"), rec.get("relevance"), rec.get("unknowns"),
         rec.get("source_type", "reporting"), rec.get("confidence", "medium"),
         1 if rec.get("trend_verified") else 0, rec.get("angle"), rec.get("topic"),
         rec.get("status", "new"), 1 if rec.get("is_demo") else 0, rec.get("provider"),
         jdump(rec.get("raw")) if rec.get("raw") is not None else None))
    return await fetch_one("SELECT * FROM sm_sources WHERE id=?", (sid,)), True


async def list_sources(status: str | None = None, include_demo: bool = True, limit: int = 200) -> list[dict]:
    sql = "SELECT * FROM sm_sources WHERE 1=1"
    args: list = []
    if status:
        sql += " AND status=?"
        args.append(status)
    if not include_demo:
        sql += " AND is_demo=0"
    sql += " ORDER BY COALESCE(published_at, discovered_at) DESC LIMIT ?"
    args.append(limit)
    return await fetch_all(sql, tuple(args))


async def update_source(source_id: str, patch: dict) -> dict | None:
    allowed = {"status", "relevance", "angle", "unknowns", "source_type", "confidence", "trend_verified",
               "topic", "summary", "event_at", "published_at", "title", "publisher"}
    fields = {k: v for k, v in patch.items() if k in allowed}
    if not fields:
        return await fetch_one("SELECT * FROM sm_sources WHERE id=?", (source_id,))
    sets = ", ".join(f"{k}=?" for k in fields) + ", updated_at=?"
    await execute(f"UPDATE sm_sources SET {sets} WHERE id=?", (*fields.values(), utc_str(), source_id))
    return await fetch_one("SELECT * FROM sm_sources WHERE id=?", (source_id,))


# ── Ideas ──────────────────────────────────────────────────────────────────

IDEA_FIELDS = ("title", "pillar", "audience", "problem", "core_message", "desired_action", "format",
               "business_goal", "measurement", "source_ids", "notes", "status", "is_demo")


async def create_idea(data: dict) -> dict:
    iid = new_id()
    vals = {k: data.get(k) for k in IDEA_FIELDS}
    vals["source_ids"] = jdump(vals.get("source_ids") or [])
    vals["status"] = vals.get("status") or "new"
    vals["is_demo"] = 1 if vals.get("is_demo") else 0
    cols = ", ".join(["id", *IDEA_FIELDS])
    await execute(f"INSERT INTO sm_ideas ({cols}) VALUES ({','.join('?' * (len(IDEA_FIELDS) + 1))})",
                  (iid, *[vals[k] for k in IDEA_FIELDS]))
    return await get_idea(iid)


async def get_idea(iid: str) -> dict | None:
    row = await fetch_one("SELECT * FROM sm_ideas WHERE id=?", (iid,))
    if row:
        row["source_ids"] = jload(row["source_ids"], [])
    return row


async def list_ideas(include_demo: bool = True, status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM sm_ideas WHERE 1=1"
    args: list = []
    if not include_demo:
        sql += " AND is_demo=0"
    if status:
        sql += " AND status=?"
        args.append(status)
    rows = await fetch_all(sql + " ORDER BY created_at DESC", tuple(args))
    for r in rows:
        r["source_ids"] = jload(r["source_ids"], [])
    return rows


async def update_idea(iid: str, patch: dict) -> dict | None:
    fields = {k: v for k, v in patch.items() if k in IDEA_FIELDS and k != "is_demo"}
    if "source_ids" in fields:
        fields["source_ids"] = jdump(fields["source_ids"] or [])
    if fields:
        sets = ", ".join(f"{k}=?" for k in fields) + ", updated_at=?"
        await execute(f"UPDATE sm_ideas SET {sets} WHERE id=?", (*fields.values(), utc_str(), iid))
    return await get_idea(iid)


# ── Content items ──────────────────────────────────────────────────────────

def _hydrate(row: dict | None) -> dict | None:
    if not row:
        return None
    row["package"] = jload(row["package"], {}) or {}
    row["asset_ids"] = jload(row["asset_ids"], []) or []
    row["sensitive_flags"] = jload(row["sensitive_flags"], []) or []
    row["fact_check"] = jload(row["fact_check"], None)
    return row


async def get_item(item_id: str) -> dict | None:
    return _hydrate(await fetch_one("SELECT * FROM sm_content_items WHERE id=?", (item_id,)))


async def get_item_raw(item_id: str) -> dict | None:
    """Row with JSON columns still as text (what approvals.compute_binding expects)."""
    return await fetch_one("SELECT * FROM sm_content_items WHERE id=?", (item_id,))


async def list_items(status: str | None = None, include_demo: bool = True,
                     fmt: str | None = None, limit: int = 300) -> list[dict]:
    sql = "SELECT * FROM sm_content_items WHERE 1=1"
    args: list = []
    if status:
        sql += " AND status=?"
        args.append(status)
    if fmt:
        sql += " AND format=?"
        args.append(fmt)
    if not include_demo:
        sql += " AND is_demo=0"
    sql += " ORDER BY COALESCE(scheduled_for, created_at) DESC LIMIT ?"
    args.append(limit)
    return [_hydrate(r) for r in await fetch_all(sql, tuple(args))]


async def create_item(data: dict, actor: str = "system") -> dict:
    item_id = new_id()
    package = data.get("package") or {}
    caption = data.get("caption") or ""
    fc = check_item(caption, package)
    await execute(
        """INSERT INTO sm_content_items (id, idea_id, format, title, pillar, audience, status, package, caption,
             asset_ids, cover_asset_id, scheduled_for, account_id, sensitive_flags, fact_check,
             production_status, review_notes, is_demo)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (item_id, data.get("idea_id"), data["format"], data["title"], data.get("pillar"), data.get("audience"),
         data.get("status", "draft"), jdump(package), caption, jdump(data.get("asset_ids") or []),
         data.get("cover_asset_id"), data.get("scheduled_for"), data.get("account_id"),
         jdump(fc["flags"]), jdump(fc), data.get("production_status", "script_only"),
         data.get("review_notes"), 1 if data.get("is_demo") else 0))
    if data.get("idea_id"):
        await execute("UPDATE sm_ideas SET status='drafted', updated_at=? WHERE id=?",
                      (utc_str(), data["idea_id"]))
    await audit(actor, "item_created", "content_item", item_id, {"format": data["format"]})
    return await get_item(item_id)


async def update_item(item_id: str, patch: dict, actor: str = "user") -> dict | None:
    """Edit fields. Publication-relevant edits invalidate an active approval."""
    item = await get_item(item_id)
    if not item:
        return None
    allowed = {"title", "pillar", "audience", "package", "caption", "asset_ids", "cover_asset_id",
               "scheduled_for", "account_id", "format", "production_status", "review_notes"}
    fields = {k: v for k, v in patch.items() if k in allowed}
    if "scheduled_for" in fields and fields["scheduled_for"]:
        # Accept local Asia/Jerusalem input and store UTC.
        utc = local_to_utc(fields["scheduled_for"])
        if utc is None:
            raise ValueError("scheduled_for אינו תאריך תקין")
        fields["scheduled_for"] = utc
    if fields.get("format") and fields["format"] not in ("reel", "carousel", "image", "story"):
        raise ValueError("format לא תקין")
    for k in ("package", "asset_ids"):
        if k in fields:
            fields[k] = jdump(fields[k] if fields[k] is not None else ({} if k == "package" else []))
    if not fields:
        return item
    publication_change = any(k in fields for k in PUBLICATION_FIELDS)
    new_caption = fields.get("caption", item["caption"])
    new_pkg = jload(fields["package"], {}) if "package" in fields else item["package"]
    fc = check_item(new_caption, new_pkg)
    fields["sensitive_flags"] = jdump(fc["flags"])
    fields["fact_check"] = jdump(fc)
    if publication_change:
        fields["version"] = item["version"] + 1
    sets = ", ".join(f"{k}=?" for k in fields) + ", updated_at=?"
    await execute(f"UPDATE sm_content_items SET {sets} WHERE id=?", (*fields.values(), utc_str(), item_id))
    raw = await get_item_raw(item_id)
    if publication_change:
        invalidated = await invalidate_if_changed(raw, actor)
        if invalidated or raw["status"] in ("approved", "scheduled"):
            # Approved/scheduled content that changed must be reviewed again; cancel queued publication.
            await execute("UPDATE sm_content_items SET status='needs_review', updated_at=? WHERE id=? "
                          "AND status IN ('approved','scheduled')", (utc_str(), item_id))
            await execute("UPDATE sm_publications SET state='cancelled', updated_at=? "
                          "WHERE content_item_id=? AND state='queued'", (utc_str(), item_id))
    await audit(actor, "item_updated", "content_item", item_id, {"fields": list(fields)})
    return await get_item(item_id)


async def set_status(item_id: str, status: str, actor: str = "user", note: str | None = None) -> dict | None:
    if status not in ITEM_STATUSES:
        raise ValueError("סטטוס לא תקין")
    await execute("UPDATE sm_content_items SET status=?, review_notes=COALESCE(?, review_notes), updated_at=? "
                  "WHERE id=?", (status, note, utc_str(), item_id))
    await audit(actor, f"item_status:{status}", "content_item", item_id, {"note": note})
    return await get_item(item_id)


async def delete_item(item_id: str, actor: str = "user") -> bool:
    item = await get_item(item_id)
    if not item:
        return False
    if item["status"] in ("publishing", "published"):
        raise ValueError("לא ניתן למחוק פריט שפורסם או בפרסום")
    await execute("UPDATE sm_publications SET state='cancelled', updated_at=? WHERE content_item_id=? "
                  "AND state IN ('queued','claimed')", (utc_str(), item_id))
    await execute("DELETE FROM sm_approvals WHERE content_item_id=?", (item_id,))
    await execute("DELETE FROM sm_content_items WHERE id=?", (item_id,))
    await audit(actor, "item_deleted", "content_item", item_id)
    return True


def count_hashtags(caption: str) -> int:
    return len(re.findall(r"(?<!\w)#\w+", caption or ""))
