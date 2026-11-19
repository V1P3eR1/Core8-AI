"""Publisher — deterministic gates, scheduling and the publication state machine.

Nothing in this module consults the LLM. Every decision is made from the
database and settings. See rules/publishing_rules.md for the human-readable
version of the same rules.

State machine (sm_publications.state):
  queued → claimed → container_created → container_ready → publish_requested
        → published | failed | needs_manual_review | cancelled
"""

import datetime
import logging

from .approvals import check_item_approval, create_approval
from .content import count_hashtags, get_item, get_item_raw, set_status
from .db import (LOCAL_TZ, audit, execute, fetch_all, fetch_one, jdump, jload, new_id, now_utc, parse_utc,
                 sha256_text, utc_str)
from .media import SPECS, get_asset, restore_grant, revoke_grant, signed_url, validate_for_instagram
from .providers.instagram import (META_DAILY_PUBLISH_LIMIT, ProviderError, ProviderTimeout, get_provider,
                                  live_account_with_token, wait_until_ready)
from .providers.notify import notifier
from .settings import get_setting, set_setting

logger = logging.getLogger("core8.social.publishing")

BACKOFF_MINUTES = (2, 10, 30)
MAX_ATTEMPTS = 3


class GateError(ValueError):
    def __init__(self, code: str, message: str, codes: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.codes = codes or [code]


# ── Account / token helpers ───────────────────────────────────────────────

async def connected_account(mode: str | None = None) -> dict | None:
    """Public-safe account summary for the current provider mode."""
    return await get_provider(mode).account()


def token_status(acct: dict | None) -> dict:
    if not acct:
        return {"ok": False, "reason": "no_account", "label": "אין חשבון מחובר"}
    exp = acct.get("token_expires_at")
    if exp:
        dt = parse_utc(exp.replace("T", " ")[:19])
        if dt and dt <= now_utc():
            return {"ok": False, "reason": "expired", "label": "הטוקן פג תוקף — יש להתחבר מחדש", "expires_at": exp}
        if dt and dt <= now_utc() + datetime.timedelta(days=7):
            return {"ok": True, "reason": "expiring", "label": "הטוקן פג בקרוב", "expires_at": exp}
    return {"ok": True, "reason": "ok", "label": "תקין", "expires_at": exp}


async def _pub_settings() -> dict:
    return await get_setting("publishing")


# ── Gates ─────────────────────────────────────────────────────────────────

async def gate_report(item: dict, for_auto: bool = False) -> dict:
    """Evaluate every gate. Returns {ok, checks:[{code, ok, label, detail}]}."""
    pub = await _pub_settings()
    provider = get_provider()
    acct = await provider.account()
    checks: list[dict] = []

    def add(code, ok, label, detail=None):
        checks.append({"code": code, "ok": bool(ok), "label": label, "detail": detail})

    add("emergency_pause", not pub.get("emergency_pause"), "השהיית חירום כבויה")
    add("mode", pub.get("mode") != "draft_only", "מצב פרסום מאפשר תזמון", pub.get("mode"))
    add("demo_vs_live", not (pub.get("demo_mode") and provider.mode == "live"),
        "לא ניתן לפרסם לחשבון אמיתי במצב demo", {"demo_mode": pub.get("demo_mode"), "provider": provider.mode})
    add("account", bool(acct), "חשבון מחובר", acct.get("username") if acct else None)
    add("account_matches", bool(acct) and (item.get("account_id") == acct.get("ig_user_id")),
        "חשבון היעד של הפריט זהה לחשבון המחובר", {"item": item.get("account_id"),
                                                 "connected": acct.get("ig_user_id") if acct else None})
    ts = token_status(acct) if provider.mode == "live" else {"ok": bool(acct), "label": "mock"}
    add("token", ts["ok"], "טוקן תקין", ts.get("label"))

    ap = await check_item_approval(await get_item_raw(item["id"]))
    add("approval", ap["valid"], "אישור פעיל התואם לגרסה הנוכחית", ap["reason"])

    flags = item.get("sensitive_flags") or []
    if for_auto:
        add("sensitive_flags", not flags, "ללא דגלי רגישות (חובה לפרסום אוטומטי)", flags)
    else:
        add("sensitive_flags", True, "דגלי רגישות נבדקו על-ידי אדם באישור", flags)

    asset_ok, asset_detail = await _assets_ok(item)
    add("assets", asset_ok, "נכסים עומדים במפרט Instagram", asset_detail)
    add("caption", len(item.get("caption") or "") <= SPECS["caption_max"]
        and count_hashtags(item.get("caption") or "") <= SPECS["hashtags_max"], "כיתוב ≤2200 תווים, ≤30 האשטגים")
    if item["format"] == "story":
        add("story_capability", (acct or {}).get("account_type", "BUSINESS") == "BUSINESS",
            "סטורי דרך API — חשבון עסקי בלבד", (acct or {}).get("account_type"))
    daily = await published_last_24h(item.get("account_id"))
    add("meta_daily_limit", daily < META_DAILY_PUBLISH_LIMIT, "מתחת למגבלת Meta (100/24h)", daily)
    if for_auto:
        auto = pub.get("auto", {})
        add("auto_category", item.get("pillar") in (auto.get("allowed_categories") or []), "קטגוריה מאושרת לאוטומט",
            item.get("pillar"))
        add("auto_account", acct and auto.get("allowed_account_id") == acct.get("ig_user_id"), "חשבון מאושר לאוטומט")
        add("auto_daily_cap", daily < int(auto.get("max_posts_per_day") or 1), "מתחת למכסת הבעלים ליום", daily)
        add("auto_window", _in_window(item.get("scheduled_for"), auto), "בתוך חלון הזמן המותר",
            {"start": auto.get("window_start"), "end": auto.get("window_end")})
        add("auto_review_topics", not set(flags) & set(auto.get("review_topics") or []),
            "לא נושא שדורש סקירה ידנית", flags)
    return {"ok": all(c["ok"] for c in checks), "checks": checks, "provider_mode": provider.mode}


def _in_window(scheduled_for_utc: str | None, auto: dict) -> bool:
    dt = parse_utc(scheduled_for_utc)
    if not dt:
        return False
    local = dt.astimezone(LOCAL_TZ)
    start = auto.get("window_start") or "00:00"
    end = auto.get("window_end") or "23:59"
    hm = local.strftime("%H:%M")
    return start <= hm <= end


async def _assets_ok(item: dict) -> tuple[bool, dict]:
    fmt = item["format"]
    ids = item.get("asset_ids") or []
    problems = []
    if fmt == "reel":
        if len(ids) != 1:
            return False, {"problems": ["רילס דורש קובץ וידאו אחד אמיתי"]}
        a = await get_asset(ids[0])
        if not a or a["media_type"] != "video":
            return False, {"problems": ["הנכס אינו וידאו — תסריט אינו וידאו"]}
        r = validate_for_instagram(a, "reel")
        problems += r["problems"]
        if item.get("cover_asset_id"):
            c = await get_asset(item["cover_asset_id"])
            if not c or c["media_type"] != "image":
                problems.append("כריכה חייבת להיות תמונה")
    elif fmt == "carousel":
        if not (SPECS["carousel"]["min_items"] <= len(ids) <= SPECS["carousel"]["max_items"]):
            return False, {"problems": ["קרוסלה דורשת 2–20 נכסים"]}
        for aid in ids:
            a = await get_asset(aid)
            if not a:
                problems.append(f"נכס חסר {aid}")
                continue
            problems += validate_for_instagram(a, "carousel_item")["problems"]
    elif fmt in ("image", "story"):
        if len(ids) != 1:
            return False, {"problems": ["נדרש נכס אחד"]}
        a = await get_asset(ids[0])
        if not a:
            return False, {"problems": ["נכס חסר"]}
        problems += validate_for_instagram(a, "image" if fmt == "image" else "story")["problems"]
    return not problems, {"problems": problems, "assets": len(ids)}


async def published_last_24h(account_id: str | None) -> int:
    if not account_id:
        return 0
    row = await fetch_one(
        "SELECT COUNT(*) AS n FROM sm_publications WHERE account_id=? AND state='published' "
        "AND published_at >= datetime('now', '-1 day')", (account_id,))
    return int(row["n"]) if row else 0


# ── Approve / schedule (human-triggered) ───────────────────────────────────

async def approve_item(item_id: str, actor: str) -> dict:
    item = await get_item(item_id)
    if not item:
        raise GateError("not_found", "פריט לא נמצא")
    pub = await _pub_settings()
    if pub.get("mode") == "draft_only":
        raise GateError("mode", "המערכת במצב 'טיוטות בלבד' — אישור לפרסום מושבת")
    acct = await connected_account()
    if not acct:
        raise GateError("account", "אין חשבון Instagram מחובר")
    if not item.get("account_id"):
        from .content import update_item
        item = await update_item(item_id, {"account_id": acct["ig_user_id"]}, actor)
    if item["account_id"] != acct["ig_user_id"]:
        raise GateError("account_matches", "חשבון היעד של הפריט אינו החשבון המחובר")
    ok, detail = await _assets_ok(item)
    if not ok:
        raise GateError("assets", "; ".join(detail["problems"]))
    approval = await create_approval(await get_item_raw(item_id), actor)
    await set_status(item_id, "approved", actor, "אושר")
    return {"item": await get_item(item_id), "approval": approval}


async def schedule_item(item_id: str, actor: str, scheduled_for_local: str | None = None) -> dict:
    """Create the publication row for an approved item. Approval must bind the schedule."""
    from .content import update_item
    if scheduled_for_local:
        # Setting the schedule changes the binding → re-approval is required by design. We set it,
        # then require the caller to approve again unless the approval already matched.
        await update_item(item_id, {"scheduled_for": scheduled_for_local}, actor)
    item = await get_item(item_id)
    if not item:
        raise GateError("not_found", "פריט לא נמצא")
    if not item.get("scheduled_for"):
        raise GateError("schedule", "חסר מועד פרסום")
    report = await gate_report(item)
    failed = [c for c in report["checks"] if not c["ok"]]
    if failed:
        raise GateError(failed[0]["code"], "חסימה: " + "; ".join(f"{c['label']}" for c in failed),
                        [c["code"] for c in failed])
    ap = await check_item_approval(await get_item_raw(item_id))
    key = f"{item_id}:{ap['binding']['binding_hash']}"
    existing = await fetch_one("SELECT * FROM sm_publications WHERE publication_key=?", (key,))
    if existing and existing["state"] not in ("cancelled", "failed"):
        raise GateError("duplicate", "כבר קיים פרסום לגרסה המאושרת הזו")
    pub_id = new_id()
    provider = get_provider()
    await execute(
        """INSERT INTO sm_publications (id, content_item_id, approval_id, publication_key, account_id, mode, state,
             scheduled_for, log) VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(publication_key) DO UPDATE SET state='queued', approval_id=excluded.approval_id,
             attempts=0, last_error=NULL, error_class=NULL, claimed_by=NULL, claimed_at=NULL, lock_expires_at=NULL,
             scheduled_for=excluded.scheduled_for, updated_at=datetime('now')""",
        (pub_id, item_id, ap["approval"]["id"], key, item["account_id"], provider.mode, "queued",
         item["scheduled_for"], jdump([{"at": utc_str(), "event": "queued", "by": actor}])))
    for aid in (item.get("asset_ids") or []) + ([item["cover_asset_id"]] if item.get("cover_asset_id") else []):
        await restore_grant(aid)
    await set_status(item_id, "scheduled", actor)
    await audit(actor, "publication_queued", "publication", pub_id, {"key": key, "mode": provider.mode})
    return await fetch_one("SELECT * FROM sm_publications WHERE publication_key=?", (key,))


async def cancel_publication(pub_id: str, actor: str) -> dict | None:
    pub = await fetch_one("SELECT * FROM sm_publications WHERE id=?", (pub_id,))
    if not pub:
        return None
    if pub["state"] not in ("queued", "claimed"):
        raise GateError("state", "ניתן לבטל רק פרסום שממתין בתור")
    await execute("UPDATE sm_publications SET state='cancelled', updated_at=? WHERE id=?", (utc_str(), pub_id))
    await set_status(pub["content_item_id"], "paused", actor, "פרסום בוטל/הושהה")
    await audit(actor, "publication_cancelled", "publication", pub_id)
    return await fetch_one("SELECT * FROM sm_publications WHERE id=?", (pub_id,))


async def set_emergency_pause(active: bool, actor: str) -> dict:
    pub = await _pub_settings()
    pub["emergency_pause"] = bool(active)
    await set_setting("publishing", pub)
    await audit(actor, "emergency_pause", "settings", None, {"active": active})
    await notifier.send("emergency_pause", "השהיית חירום " + ("הופעלה" if active else "בוטלה"), {"by": actor})
    return pub


# ── Automatic mode (worker-triggered) ──────────────────────────────────────

async def auto_schedule_candidates(actor: str = "worker:auto") -> list[dict]:
    """In automatic mode, approve+queue items in 'needs_review' that pass EVERY auto gate.
    Items with sensitive flags never pass. Returns the publications created."""
    pub = await _pub_settings()
    if pub.get("mode") != "automatic" or pub.get("emergency_pause"):
        return []
    out = []
    for item in await fetch_all("SELECT id FROM sm_content_items WHERE status='needs_review' AND is_demo=0 "
                                "AND scheduled_for IS NOT NULL ORDER BY scheduled_for"):
        full = await get_item(item["id"])
        acct = await connected_account()
        if not acct:
            break
        if full.get("account_id") != acct["ig_user_id"]:
            continue
        # approval is created by the system *only* after all auto gates pass
        pre = await gate_report(full, for_auto=True)
        blocking = [c["code"] for c in pre["checks"] if not c["ok"] and c["code"] != "approval"]
        if blocking:
            continue
        await create_approval(await get_item_raw(full["id"]), actor)
        try:
            out.append(await schedule_item(full["id"], actor))
        except GateError as e:
            await audit(actor, "auto_schedule_blocked", "content_item", full["id"], {"code": e.code, "msg": str(e)})
    return out


# ── Worker: claim + run one publication ────────────────────────────────────

async def claim_due_publications(worker_id: str, lock_seconds: int, limit: int = 5) -> list[dict]:
    """Transactional claim: each UPDATE only succeeds for one worker."""
    now = utc_str()
    lock_until = utc_str(now_utc() + datetime.timedelta(seconds=lock_seconds))
    rows = await fetch_all(
        "SELECT id FROM sm_publications WHERE scheduled_for <= ? AND (state='queued' OR "
        "(state IN ('claimed','container_created','container_ready') AND lock_expires_at < ?)) "
        "ORDER BY scheduled_for LIMIT ?", (now, now, limit))
    claimed = []
    for r in rows:
        n = await execute(
            "UPDATE sm_publications SET state='claimed', claimed_by=?, claimed_at=?, lock_expires_at=?, "
            "updated_at=? WHERE id=? AND (state='queued' OR (state IN ('claimed','container_created','container_ready') "
            "AND lock_expires_at < ?))", (worker_id, now, lock_until, now, r["id"], now))
        if n == 1:
            claimed.append(await fetch_one("SELECT * FROM sm_publications WHERE id=?", (r["id"],)))
    return claimed


async def _log(pub_id: str, event: str, **detail) -> None:
    row = await fetch_one("SELECT log FROM sm_publications WHERE id=?", (pub_id,))
    log = jload(row["log"], []) if row else []
    log.append({"at": utc_str(), "event": event, **{k: v for k, v in detail.items() if v is not None}})
    await execute("UPDATE sm_publications SET log=?, updated_at=? WHERE id=?", (jdump(log[-50:]), utc_str(), pub_id))


async def _set_state(pub_id: str, state: str, **fields) -> None:
    sets = ", ".join(f"{k}=?" for k in fields)
    await execute(f"UPDATE sm_publications SET state=?, {sets + ', ' if sets else ''}updated_at=? WHERE id=?",
                  (state, *fields.values(), utc_str(), pub_id))
    await _log(pub_id, state)


async def run_publication(pub: dict, worker_id: str = "worker") -> dict:
    """Execute one claimed publication end-to-end. Returns the final row."""
    pub_id = pub["id"]
    item = await get_item(pub["content_item_id"])
    provider = get_provider(pub["mode"])
    try:
        if not item:
            raise ProviderError("content item missing", retryable=False)
        # Re-check every gate at execution time (settings may have changed since queueing).
        report = await gate_report(item, for_auto=await _is_auto(pub))
        failed = [c for c in report["checks"] if not c["ok"]]
        if failed:
            codes = [c["code"] for c in failed]
            if "emergency_pause" in codes or "mode" in codes:
                await _set_state(pub_id, "cancelled", last_error="חסימה: " + ", ".join(codes), error_class="permanent")
                await set_status(item["id"], "paused", worker_id, "הפרסום נעצר: " + ", ".join(codes))
            else:
                await _set_state(pub_id, "failed", last_error="חסימה: " + ", ".join(codes), error_class="permanent")
                await set_status(item["id"], "failed", worker_id, "נכשל בבדיקות לפני פרסום: " + ", ".join(codes))
            return await fetch_one("SELECT * FROM sm_publications WHERE id=?", (pub_id,))

        await set_status(item["id"], "publishing", worker_id)
        token, ig_user_id = await _credentials(pub["mode"], item)

        if pub.get("provider_media_id"):
            return await _finalize_published(pub_id, item, pub["provider_media_id"], provider, token)

        container_id = pub.get("container_id")
        if not container_id:
            container_id, children = await _create_containers(provider, ig_user_id, token, item)
            await _set_state(pub_id, "container_created", container_id=container_id,
                             child_container_ids=jdump(children))
        await wait_until_ready(provider, container_id, token)
        await _set_state(pub_id, "container_ready")

        # Point of no return: once we send media_publish the outcome may be unknown.
        await _set_state(pub_id, "publish_requested", publish_requested_at=utc_str(),
                         attempts=pub["attempts"] + 1)
        try:
            media_id = await provider.publish(ig_user_id, token, container_id)
        except ProviderTimeout as e:
            await _log(pub_id, "timeout_after_publish", error=str(e))
            return await reconcile(pub_id, provider, token, ig_user_id)
        return await _finalize_published(pub_id, item, media_id, provider, token)

    except ProviderTimeout as e:
        await _set_state(pub_id, "needs_manual_review", last_error=str(e), error_class="unknown")
        await set_status(item["id"], "needs_manual_review", worker_id, str(e))
    except ProviderError as e:
        await _handle_provider_error(pub, item, e, worker_id)
    except Exception as e:  # defensive: never leave the row locked
        logger.exception("publication %s crashed", pub_id)
        await _set_state(pub_id, "needs_manual_review", last_error=f"{type(e).__name__}: {e}"[:300],
                         error_class="unknown")
        if item:
            await set_status(item["id"], "needs_manual_review", worker_id, "שגיאה פנימית — דורש בדיקה")
    finally:
        await _revoke_grants(item)
    return await fetch_one("SELECT * FROM sm_publications WHERE id=?", (pub_id,))


async def _is_auto(pub: dict) -> bool:
    if not pub.get("approval_id"):
        return False
    row = await fetch_one("SELECT approved_by FROM sm_approvals WHERE id=?", (pub["approval_id"],))
    return bool(row and (row["approved_by"] or "").startswith("worker:auto"))


async def _credentials(mode: str, item: dict) -> tuple[str, str]:
    if mode == "live":
        acct = await live_account_with_token()
        if not acct:
            raise ProviderError("אין חשבון מחובר", retryable=False, code=190)
        if acct["ig_user_id"] != item.get("account_id"):
            raise ProviderError("חשבון מחובר שונה מחשבון היעד", retryable=False)
        ts = token_status(acct)
        if not ts["ok"]:
            raise ProviderError("הטוקן פג תוקף", retryable=False, code=190)
        return acct["access_token"], acct["ig_user_id"]
    return "mock-token", item.get("account_id") or "mock"


async def _create_containers(provider, ig_user_id: str, token: str, item: dict) -> tuple[str, list[str]]:
    pkg = item.get("package") or {}
    fmt = item["format"]
    ids = item["asset_ids"]
    caption = item.get("caption") or ""
    if fmt == "image":
        a = await get_asset(ids[0])
        cid = await provider.create_container(ig_user_id, token, image_url=signed_url(a["id"]), caption=caption,
                                              alt_text=(pkg.get("alt_text") or None), **_ai_flag(pkg))
        return cid, []
    if fmt == "reel":
        a = await get_asset(ids[0])
        cover = await get_asset(item["cover_asset_id"]) if item.get("cover_asset_id") else None
        cid = await provider.create_container(
            ig_user_id, token, media_type="REELS", video_url=signed_url(a["id"]), caption=caption,
            cover_url=signed_url(cover["id"]) if cover else None,
            share_to_feed="true" if pkg.get("share_to_feed", True) else "false", **_ai_flag(pkg))
        return cid, []
    if fmt == "story":
        a = await get_asset(ids[0])
        kw = {"image_url": signed_url(a["id"])} if a["media_type"] == "image" else {"video_url": signed_url(a["id"])}
        cid = await provider.create_container(ig_user_id, token, media_type="STORIES", **kw)
        return cid, []
    # carousel: children first, then the parent
    children = []
    for aid in ids:
        a = await get_asset(aid)
        kw = {"image_url": signed_url(aid)} if a["media_type"] == "image" else {"video_url": signed_url(aid)}
        children.append(await provider.create_container(ig_user_id, token, is_carousel_item="true", **kw))
    for c in children:
        await wait_until_ready(provider, c, token)
    parent = await provider.create_container(ig_user_id, token, media_type="CAROUSEL", children=",".join(children),
                                             caption=caption, **_ai_flag(pkg))
    return parent, children


def _ai_flag(pkg: dict) -> dict:
    """AI Info label (Instagram changelog 2026-06-22): sent only when the owner marked the item as AI-generated."""
    return {"is_ai_generated": "true"} if pkg.get("is_ai_generated") else {}


async def _finalize_published(pub_id: str, item: dict, media_id: str, provider, token: str) -> dict:
    permalink = None
    try:
        info = await provider.media_info(media_id, token)
        permalink = info.get("permalink")
    except ProviderError:
        pass
    await _set_state(pub_id, "published", provider_media_id=media_id, permalink=permalink, published_at=utc_str())
    await execute("UPDATE sm_approvals SET status='consumed' WHERE id=(SELECT approval_id FROM sm_publications WHERE id=?)",
                  (pub_id,))
    await set_status(item["id"], "published", "worker", f"פורסם. media id: {media_id}")
    await notifier.send("published", f"פורסם: {item['title']}", {"media_id": media_id, "permalink": permalink,
                                                               "mode": provider.mode})
    return await fetch_one("SELECT * FROM sm_publications WHERE id=?", (pub_id,))


async def _handle_provider_error(pub: dict, item: dict | None, e: ProviderError, worker_id: str) -> None:
    pub_id = pub["id"]
    attempts = (pub.get("attempts") or 0) + 1
    if e.retryable and attempts < MAX_ATTEMPTS:
        delay = BACKOFF_MINUTES[min(attempts - 1, len(BACKOFF_MINUTES) - 1)]
        next_at = utc_str(now_utc() + datetime.timedelta(minutes=delay))
        await execute("UPDATE sm_publications SET state='queued', attempts=?, last_error=?, error_class='retryable', "
                      "scheduled_for=?, claimed_by=NULL, lock_expires_at=NULL, updated_at=? WHERE id=?",
                      (attempts, str(e)[:300], next_at, utc_str(), pub_id))
        await _log(pub_id, "retry_scheduled", attempt=attempts, next_at=next_at, error=str(e)[:200])
        if item:
            await set_status(item["id"], "scheduled", worker_id, f"ניסיון חוזר {attempts}/{MAX_ATTEMPTS}: {e}")
        return
    await execute("UPDATE sm_publications SET state='failed', attempts=?, last_error=?, error_class=?, updated_at=? "
                  "WHERE id=?", (attempts, str(e)[:300], "retryable_exhausted" if e.retryable else "permanent",
                                 utc_str(), pub_id))
    await _log(pub_id, "failed", error=str(e)[:200], code=e.code)
    if item:
        await set_status(item["id"], "failed", worker_id, str(e)[:300])
    await notifier.send("publish_failed", f"פרסום נכשל: {item['title'] if item else pub_id}", {"error": str(e)[:200]})


async def _revoke_grants(item: dict | None) -> None:
    if not item:
        return
    pub = await fetch_one("SELECT state FROM sm_publications WHERE content_item_id=? ORDER BY updated_at DESC LIMIT 1",
                          (item["id"],))
    if pub and pub["state"] in ("published", "failed", "cancelled", "needs_manual_review"):
        for aid in (item.get("asset_ids") or []) + ([item["cover_asset_id"]] if item.get("cover_asset_id") else []):
            await revoke_grant(aid)


# ── Reconciliation (ambiguous outcome) ─────────────────────────────────────

async def reconcile(pub_id: str, provider=None, token: str | None = None, ig_user_id: str | None = None,
                    actor: str = "worker") -> dict:
    """Determine the real outcome of a publication whose request may or may not have landed.
    Never re-sends media_publish. Ends in published or needs_manual_review."""
    pub = await fetch_one("SELECT * FROM sm_publications WHERE id=?", (pub_id,))
    item = await get_item(pub["content_item_id"])
    provider = provider or get_provider(pub["mode"])
    if token is None:
        try:
            token, ig_user_id = await _credentials(pub["mode"], item)
        except ProviderError as e:
            await _set_state(pub_id, "needs_manual_review", last_error=f"reconcile: {e}", error_class="unknown")
            await set_status(item["id"], "needs_manual_review", actor, "לא ניתן לאמת תוצאה: " + str(e))
            return await fetch_one("SELECT * FROM sm_publications WHERE id=?", (pub_id,))
    try:
        if pub.get("provider_media_id"):
            return await _finalize_published(pub_id, item, pub["provider_media_id"], provider, token)
        status = await provider.container_status(pub["container_id"], token) if pub.get("container_id") else "UNKNOWN"
        await _log(pub_id, "reconcile_container_status", status=status)
        if status == "PUBLISHED":
            # Find the media id by matching the caption among recent media.
            cap_hash = sha256_text(item.get("caption") or "")
            for m in await provider.recent_media(ig_user_id, token, limit=10):
                if sha256_text(m.get("caption") or "") == cap_hash:
                    return await _finalize_published(pub_id, item, m["id"], provider, token)
            await _set_state(pub_id, "needs_manual_review", error_class="unknown",
                             last_error="הקונטיינר מדווח PUBLISHED אך media id לא אותר — יש לאמת ידנית באינסטגרם")
        elif status in ("FINISHED", "IN_PROGRESS"):
            await _set_state(pub_id, "needs_manual_review", error_class="unknown",
                             last_error=f"בקשת הפרסום נשלחה אך הסטטוס הוא {status}; לא נשלחת שוב אוטומטית")
        else:
            await _set_state(pub_id, "needs_manual_review", error_class="unknown",
                             last_error=f"תוצאה לא ידועה (status={status}). יש לבדוק ידנית לפני ניסיון חוזר")
    except ProviderError as e:
        await _set_state(pub_id, "needs_manual_review", last_error=f"reconcile: {e}"[:300], error_class="unknown")
    row = await fetch_one("SELECT * FROM sm_publications WHERE id=?", (pub_id,))
    if row["state"] == "needs_manual_review":
        await set_status(item["id"], "needs_manual_review", actor, row["last_error"])
        await notifier.send("needs_manual_review", f"דורש בדיקה ידנית: {item['title']}", {"error": row["last_error"]})
    return row


async def manual_resolve(pub_id: str, outcome: str, actor: str, provider_media_id: str | None = None,
                         note: str | None = None) -> dict:
    """Owner decision after manual verification: 'published' (with the real media id) or 'failed'."""
    pub = await fetch_one("SELECT * FROM sm_publications WHERE id=?", (pub_id,))
    if not pub or pub["state"] != "needs_manual_review":
        raise GateError("state", "רק פרסום במצב 'דורש בדיקה ידנית' ניתן לסגירה ידנית")
    if outcome == "published":
        if not provider_media_id:
            raise GateError("media_id", "יש להזין את ה-media id האמיתי מאינסטגרם")
        await _set_state(pub_id, "published", provider_media_id=provider_media_id, published_at=utc_str(),
                         last_error=None)
        await set_status(pub["content_item_id"], "published", actor, note or "אומת ידנית")
    elif outcome == "failed":
        await _set_state(pub_id, "failed", error_class="permanent", last_error=note or "סומן ככישלון ידנית")
        await set_status(pub["content_item_id"], "failed", actor, note or "סומן ככישלון ידנית")
    else:
        raise GateError("outcome", "outcome חייב להיות published או failed")
    await audit(actor, f"manual_resolve:{outcome}", "publication", pub_id, {"note": note})
    return await fetch_one("SELECT * FROM sm_publications WHERE id=?", (pub_id,))


async def list_publications(limit: int = 100) -> list[dict]:
    rows = await fetch_all(
        "SELECT p.*, i.title, i.format, i.is_demo FROM sm_publications p JOIN sm_content_items i ON i.id=p.content_item_id "
        "ORDER BY p.scheduled_for DESC LIMIT ?", (limit,))
    for r in rows:
        r["log"] = jload(r["log"], [])
        r["child_container_ids"] = jload(r.get("child_container_ids"), [])
    return rows
