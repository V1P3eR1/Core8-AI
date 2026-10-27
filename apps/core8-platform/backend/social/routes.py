"""Core8AI Social Manager REST API — /api/social/*

Every route is JWT-protected except `media-public` (HMAC-signed, time-limited
URLs that Meta fetches). The LLM never reaches these routes; a human or the
worker does. Responses carry `provider_mode` / `is_demo` so the UI can label
what is real.
"""

import logging
import os
import json
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config import cfg as platform_cfg
from security.jwt_auth import require_jwt
from tools.instagram_api import GraphAPIError, OAUTH_SCOPES, build_oauth_url

from . import agents, carousel_render, content, jobs, leads, metrics, publishing, reports
from .config import scfg
from .db import audit, execute, fetch_all, fetch_one, utc_to_local_iso, utc_str
from .demo_data import clear_demo, seed_demo
from .media import (ALLOWED_MIME, asset_path, delete_asset, get_asset, is_revoked, list_assets, save_upload,
                    validate_for_instagram, verify_signature)
from .planner import propose_calendar
from .providers.instagram import get_provider, live_account_with_token, mock_provider
from .providers.llm import llm
from .providers.notify import notifier
from .providers.research import research
from .settings import DEFAULT_PUBLISHING, PILLARS, get_setting, set_setting

logger = logging.getLogger("core8.social.api")

router = APIRouter(prefix="/api/social", tags=["social"], dependencies=[Depends(require_jwt)])
public_router = APIRouter(prefix="/api/social", tags=["social-public"])


def _actor(payload: dict) -> str:
    return payload.get("email") or payload.get("sub") or "user"


def _err(e: Exception, status: int = 400):
    raise HTTPException(status_code=status, detail=str(e))


async def _include_demo() -> bool:
    return bool((await get_setting("publishing")).get("demo_mode", True))


def _local(row: dict, *keys: str) -> dict:
    for k in keys:
        if row.get(k):
            row[k + "_local"] = utc_to_local_iso(row[k])
    return row


# ── Overview ───────────────────────────────────────────────────────────────

@router.get("/overview")
async def overview():
    pub = await get_setting("publishing")
    provider = get_provider()
    acct = await provider.account()
    counts = {}
    for key, sql in {
        "sources_new": "SELECT COUNT(*) n FROM sm_sources WHERE status='new'",
        "ideas_new": "SELECT COUNT(*) n FROM sm_ideas WHERE status IN ('new','shortlisted')",
        "items_needs_review": "SELECT COUNT(*) n FROM sm_content_items WHERE status='needs_review'",
        "items_scheduled": "SELECT COUNT(*) n FROM sm_content_items WHERE status='scheduled'",
        "items_manual_review": "SELECT COUNT(*) n FROM sm_content_items WHERE status='needs_manual_review'",
        "publications_failed": "SELECT COUNT(*) n FROM sm_publications WHERE state='failed'",
        "leads_open": "SELECT COUNT(*) n FROM sm_leads WHERE status IN ('new','contacted','qualified','proposal')",
        "jobs_failed": "SELECT COUNT(*) n FROM sm_jobs WHERE status='failed'",
        "demo_records": "SELECT (SELECT COUNT(*) FROM sm_sources WHERE is_demo=1)+(SELECT COUNT(*) FROM sm_ideas WHERE is_demo=1)"
                        "+(SELECT COUNT(*) FROM sm_content_items WHERE is_demo=1)+(SELECT COUNT(*) FROM sm_leads WHERE is_demo=1) n",
    }.items():
        row = await fetch_one(sql)
        counts[key] = int(row["n"]) if row else 0
    upcoming = [_local(r, "scheduled_for") for r in await fetch_all(
        "SELECT id, title, format, status, scheduled_for, is_demo FROM sm_content_items WHERE status IN ('scheduled','approved') "
        "ORDER BY scheduled_for LIMIT 8")]
    return {
        "modes": {"instagram": provider.mode, "llm": llm.mode, "research": research.mode,
                  "notify": notifier.mode},
        "publishing": pub, "account": acct, "token": publishing.token_status(acct) if provider.mode == "live" else
        {"ok": bool(acct), "label": "mock — אין טוקן אמיתי"},
        "worker": await jobs.worker_status(), "counts": counts, "upcoming": upcoming,
        "timezone": scfg.timezone, "pillars": PILLARS,
    }


# ── Settings ───────────────────────────────────────────────────────────────

SETTING_KEYS = ("brand", "publishing", "content_mix")


@router.get("/settings")
async def settings_all():
    return {k: await get_setting(k) for k in SETTING_KEYS}


@router.get("/settings/{key}")
async def settings_get(key: str):
    if key not in SETTING_KEYS:
        raise HTTPException(404)
    return await get_setting(key)


class SettingBody(BaseModel):
    value: dict


@router.put("/settings/{key}")
async def settings_put(key: str, body: SettingBody, payload: dict = Depends(require_jwt)):
    if key not in SETTING_KEYS:
        raise HTTPException(404)
    value = body.value
    if key == "publishing":
        current = await get_setting("publishing")
        if value.get("mode") not in ("draft_only", "approval_required", "automatic"):
            raise HTTPException(400, "mode לא תקין")
        if value["mode"] == "automatic":
            auto = value.get("auto") or {}
            if not auto.get("allowed_categories") or not auto.get("allowed_account_id"):
                raise HTTPException(400, "פרסום אוטומטי דורש קטגוריות מאושרות וחשבון מאושר")
            if not value.get("confirm_automatic"):
                raise HTTPException(400, "הפעלת פרסום אוטומטי דורשת אישור מפורש (confirm_automatic=true)")
        # emergency pause is only changed through its own endpoint
        value["emergency_pause"] = current.get("emergency_pause", False)
        value.pop("confirm_automatic", None)
        value = {**DEFAULT_PUBLISHING, **value, "auto": {**DEFAULT_PUBLISHING["auto"], **(value.get("auto") or {})}}
        await audit(_actor(payload), "publishing_settings", "settings", None,
                    {"mode": value["mode"], "demo_mode": value.get("demo_mode")})
    out = await set_setting(key, value)
    await audit(_actor(payload), f"settings_updated:{key}", "settings")
    return out


class PauseBody(BaseModel):
    active: bool


@router.post("/settings/emergency-pause")
async def emergency_pause(body: PauseBody, payload: dict = Depends(require_jwt)):
    return await publishing.set_emergency_pause(body.active, _actor(payload))


@router.post("/demo/seed")
async def demo_seed(payload: dict = Depends(require_jwt)):
    out = await seed_demo()
    await audit(_actor(payload), "demo_seeded", "demo", None, out)
    return out


@router.post("/starter-pack/seed")
async def starter_pack_seed(payload: dict = Depends(require_jwt)):
    """Real sources + original drafts collected in the build session (not demo data)."""
    from .starter_pack import seed_starter_pack
    return await seed_starter_pack(_actor(payload))


@router.post("/demo/clear")
async def demo_clear(payload: dict = Depends(require_jwt)):
    out = await clear_demo()
    await audit(_actor(payload), "demo_cleared", "demo", None, out)
    return out


# ── Research ───────────────────────────────────────────────────────────────

@router.get("/sources")
async def sources_list(status: str | None = None):
    rows = await content.list_sources(status=status, include_demo=await _include_demo())
    return {"provider_mode": research.mode, "llm_mode": llm.mode, "feeds": research.feeds if research.mode == "live" else [],
            "items": [_local(r, "published_at", "discovered_at", "event_at") for r in rows]}


class SourceIn(BaseModel):
    title: str
    url: str
    publisher: str | None = None
    published_at: str | None = None
    event_at: str | None = None
    summary: str | None = None
    relevance: str | None = None
    unknowns: str | None = None
    source_type: Literal["official", "reporting", "opinion", "inference", "benchmark"] = "reporting"
    confidence: Literal["low", "medium", "high"] = "medium"
    angle: str | None = None
    topic: str | None = None


@router.post("/sources", status_code=201)
async def sources_add(body: SourceIn, payload: dict = Depends(require_jwt)):
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL לא תקין")
    row, created = await content.upsert_source({**body.model_dump(), "provider": "manual", "is_demo": 0})
    await audit(_actor(payload), "source_added" if created else "source_duplicate", "source", row["id"])
    return {"created": created, "source": row}


@router.patch("/sources/{sid}")
async def sources_patch(sid: str, body: dict, payload: dict = Depends(require_jwt)):
    row = await content.update_source(sid, body)
    if not row:
        raise HTTPException(404)
    await audit(_actor(payload), "source_updated", "source", sid, {"fields": list(body)})
    return row


@router.post("/research/run")
async def research_run(run_now: bool = True, payload: dict = Depends(require_jwt)):
    job = await jobs.enqueue("research", {"max_per_feed": 8})
    if run_now:
        claimed = await _claim_specific(job["id"])
        if claimed:
            job = await jobs.run_job(claimed, "api:" + _actor(payload))
    return {"job": job, "provider_mode": research.mode}


async def _claim_specific(job_id: str) -> dict | None:
    n = await execute("UPDATE sm_jobs SET status='running', claimed_by='api', claimed_at=?, started_at=?, attempts=attempts+1 "
                      "WHERE id=? AND status='pending'", (utc_str(), utc_str(), job_id))
    return await fetch_one("SELECT * FROM sm_jobs WHERE id=?", (job_id,)) if n == 1 else None


# ── Ideas ──────────────────────────────────────────────────────────────────

@router.get("/ideas")
async def ideas_list(status: str | None = None):
    return {"llm_mode": llm.mode, "items": await content.list_ideas(include_demo=await _include_demo(), status=status)}


class IdeaIn(BaseModel):
    title: str
    pillar: str
    audience: Literal["smb", "enterprise", "founders"]
    problem: str
    core_message: str
    desired_action: str
    format: Literal["reel", "carousel", "image", "story"]
    business_goal: str
    measurement: str
    source_ids: list[str] = Field(default_factory=list)
    notes: str | None = None


@router.post("/ideas", status_code=201)
async def ideas_add(body: IdeaIn, payload: dict = Depends(require_jwt)):
    if body.pillar not in {p["key"] for p in PILLARS}:
        raise HTTPException(400, "pillar לא תקין")
    idea = await content.create_idea(body.model_dump())
    await audit(_actor(payload), "idea_created", "idea", idea["id"])
    return idea


@router.patch("/ideas/{iid}")
async def ideas_patch(iid: str, body: dict):
    row = await content.update_idea(iid, body)
    if not row:
        raise HTTPException(404)
    return row


@router.post("/ideas/generate")
async def ideas_generate(count: int = Query(20, ge=1, le=40), payload: dict = Depends(require_jwt)):
    created = await agents.generate_ideas(count=count)
    return {"llm_mode": llm.mode, "created": len(created), "items": created}


class DraftIn(BaseModel):
    format: Literal["reel", "carousel", "image", "story"] | None = None


@router.post("/ideas/{iid}/draft", status_code=201)
async def ideas_draft(iid: str, body: DraftIn, payload: dict = Depends(require_jwt)):
    idea = await content.get_idea(iid)
    if not idea:
        raise HTTPException(404)
    return await agents.draft_package(idea, body.format, actor=_actor(payload))


# ── Content items ──────────────────────────────────────────────────────────

@router.get("/items")
async def items_list(status: str | None = None, format: str | None = None):
    rows = await content.list_items(status=status, include_demo=await _include_demo(), fmt=format)
    return {"items": [_local(r, "scheduled_for") for r in rows]}


@router.get("/items/{item_id}")
async def items_get(item_id: str):
    item = await content.get_item(item_id)
    if not item:
        raise HTTPException(404)
    assets = [await get_asset(a) for a in item["asset_ids"]]
    item["assets"] = [a for a in assets if a]
    item["cover_asset"] = await get_asset(item["cover_asset_id"]) if item.get("cover_asset_id") else None
    item["approval"] = await publishing.check_item_approval(await content.get_item_raw(item_id))
    item["approval"].pop("binding", None)
    item["publications"] = [p for p in await publishing.list_publications(200) if p["content_item_id"] == item_id]
    return _local(item, "scheduled_for")


class ItemIn(BaseModel):
    format: Literal["reel", "carousel", "image", "story"]
    title: str
    pillar: str | None = None
    audience: str | None = None
    caption: str = ""
    package: dict = Field(default_factory=dict)
    idea_id: str | None = None


@router.post("/items", status_code=201)
async def items_create(body: ItemIn, payload: dict = Depends(require_jwt)):
    data = body.model_dump()
    data["package"] = agents.producer_enrich(data["package"], data["format"])
    return await content.create_item(data, actor=_actor(payload))


@router.patch("/items/{item_id}")
async def items_patch(item_id: str, body: dict, payload: dict = Depends(require_jwt)):
    try:
        row = await content.update_item(item_id, body, _actor(payload))
    except ValueError as e:
        _err(e)
    if not row:
        raise HTTPException(404)
    return _local(row, "scheduled_for")


@router.delete("/items/{item_id}")
async def items_delete(item_id: str, payload: dict = Depends(require_jwt)):
    try:
        ok = await content.delete_item(item_id, _actor(payload))
    except ValueError as e:
        _err(e)
    if not ok:
        raise HTTPException(404)
    return {"deleted": True}


class StatusIn(BaseModel):
    status: Literal["draft", "needs_review", "rejected", "paused"]
    note: str | None = None


@router.post("/items/{item_id}/status")
async def items_status(item_id: str, body: StatusIn, payload: dict = Depends(require_jwt)):
    item = await content.get_item(item_id)
    if not item:
        raise HTTPException(404)
    if item["status"] in ("publishing", "published"):
        raise HTTPException(400, "לא ניתן לשנות סטטוס של פריט שפורסם")
    if body.status == "paused":
        for p in await fetch_all("SELECT id FROM sm_publications WHERE content_item_id=? AND state IN ('queued','claimed')", (item_id,)):
            await publishing.cancel_publication(p["id"], _actor(payload))
    return await content.set_status(item_id, body.status, _actor(payload), body.note)


@router.get("/items/{item_id}/gates")
async def items_gates(item_id: str, for_auto: bool = False):
    item = await content.get_item(item_id)
    if not item:
        raise HTTPException(404)
    return await publishing.gate_report(item, for_auto=for_auto)


@router.post("/items/{item_id}/approve")
async def items_approve(item_id: str, payload: dict = Depends(require_jwt)):
    try:
        return await publishing.approve_item(item_id, _actor(payload))
    except publishing.GateError as e:
        raise HTTPException(400, {"code": e.code, "codes": e.codes, "message": str(e)})


class ScheduleIn(BaseModel):
    scheduled_for: str | None = None  # local Asia/Jerusalem ISO, e.g. 2026-11-02T18:00


@router.post("/items/{item_id}/schedule")
async def items_schedule(item_id: str, body: ScheduleIn, payload: dict = Depends(require_jwt)):
    try:
        if body.scheduled_for:
            # schedule is part of the approval binding: set it, then approve, then queue
            await content.update_item(item_id, {"scheduled_for": body.scheduled_for}, _actor(payload))
            await publishing.approve_item(item_id, _actor(payload))
        pub = await publishing.schedule_item(item_id, _actor(payload))
    except publishing.GateError as e:
        raise HTTPException(400, {"code": e.code, "codes": e.codes, "message": str(e)})
    except ValueError as e:
        _err(e)
    return _local(pub, "scheduled_for")


class RenderIn(BaseModel):
    template: str | None = None


@router.post("/items/{item_id}/render-carousel")
async def items_render(item_id: str, body: RenderIn, payload: dict = Depends(require_jwt)):
    item = await content.get_item(item_id)
    if not item or item["format"] != "carousel":
        raise HTTPException(404, "פריט קרוסלה לא נמצא")
    try:
        assets = await carousel_render.render_carousel(item, body.template, _actor(payload))
    except ValueError as e:
        _err(e)
    pkg = {**item["package"], "template": body.template or item["package"].get("template"),
           "production_status": "ready_to_publish"}
    row = await content.update_item(item_id, {"asset_ids": [a["id"] for a in assets], "package": pkg,
                                              "production_status": "ready_to_publish"}, _actor(payload))
    return {"assets": assets, "item": row, "raqm": carousel_render.raqm_available()}


# ── Carousel templates ─────────────────────────────────────────────────────

@router.get("/carousel/templates")
async def templates_get():
    return await carousel_render.get_templates()


@router.put("/carousel/templates")
async def templates_put(body: dict, payload: dict = Depends(require_jwt)):
    try:
        return await carousel_render.save_templates(body)
    except ValueError as e:
        _err(e)


class PreviewIn(BaseModel):
    slide: dict
    template: str | None = None
    index: int = 0
    total: int = 1
    is_demo: bool = False


@router.post("/carousel/preview")
async def templates_preview(body: PreviewIn):
    data = await carousel_render.preview_slide_bytes(body.slide, body.template, body.index, body.total, body.is_demo)
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


# ── Assets ─────────────────────────────────────────────────────────────────

@router.get("/assets")
async def assets_list():
    return {"items": await list_assets(include_demo=await _include_demo()), "allowed_mime": list(ALLOWED_MIME),
            "max_upload_mb": scfg.max_upload_bytes // (1024 * 1024)}


@router.post("/assets", status_code=201)
async def assets_upload(file: UploadFile = File(...), ownership: str = Form("owner_upload"),
                        permission_note: str = Form(None), alt_text: str = Form(None), caption: str = Form(None),
                        brief: str = Form(None), payload: dict = Depends(require_jwt)):
    data = await file.read()
    mime = (file.content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME:
        ext = (file.filename or "").rsplit(".", 1)[-1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "mp4": "video/mp4", "mov": "video/quicktime"}.get(ext, mime)
    if ownership not in ("owner_upload", "rendered", "generated", "third_party"):
        raise HTTPException(400, "ownership לא תקין")
    try:
        asset = await save_upload(data, file.filename or "upload", mime, ownership, permission_note, 0, alt_text, caption, brief)
    except ValueError as e:
        _err(e)
    await audit(_actor(payload), "asset_uploaded", "asset", asset["id"], {"bytes": asset["bytes"], "mime": mime})
    return asset


@router.patch("/assets/{aid}")
async def assets_patch(aid: str, body: dict, payload: dict = Depends(require_jwt)):
    fields = {k: v for k, v in body.items() if k in ("alt_text", "caption", "brief", "permission_note", "ownership")}
    if fields:
        sets = ", ".join(f"{k}=?" for k in fields)
        await execute(f"UPDATE sm_assets SET {sets} WHERE id=?", (*fields.values(), aid))
    a = await get_asset(aid)
    if not a:
        raise HTTPException(404)
    return a


@router.get("/assets/{aid}/check")
async def assets_check(aid: str, usage: Literal["image", "carousel_item", "reel", "story"] = "image"):
    a = await get_asset(aid)
    if not a:
        raise HTTPException(404)
    return validate_for_instagram(a, usage)


@router.get("/assets/{aid}/file")
async def assets_file(aid: str):
    a = await get_asset(aid)
    if not a or not os.path.exists(asset_path(a)):
        raise HTTPException(404)
    return FileResponse(asset_path(a), media_type=a["mime"])


@router.delete("/assets/{aid}")
async def assets_delete(aid: str, payload: dict = Depends(require_jwt)):
    used = await fetch_one("SELECT id FROM sm_content_items WHERE asset_ids LIKE ? AND status IN ('scheduled','publishing')",
                           (f"%{aid}%",))
    if used:
        raise HTTPException(400, "הנכס משויך לפריט מתוזמן — יש להשהות אותו קודם")
    if not await delete_asset(aid):
        raise HTTPException(404)
    await audit(_actor(payload), "asset_deleted", "asset", aid)
    return {"deleted": True}


@public_router.get("/media-public/{aid}")
async def media_public(aid: str, exp: int = 0, sig: str = ""):
    """Time-limited, HMAC-signed URL for Meta to fetch media. Revoked once the publication is final."""
    if not verify_signature(aid, exp, sig) or await is_revoked(aid):
        raise HTTPException(404)
    a = await get_asset(aid)
    if not a or not os.path.exists(asset_path(a)):
        raise HTTPException(404)
    return FileResponse(asset_path(a), media_type=a["mime"], headers={"Cache-Control": "private, max-age=0"})


# ── Publications ───────────────────────────────────────────────────────────

@router.get("/publications")
async def publications_list():
    return {"provider_mode": get_provider().mode,
            "items": [_local(p, "scheduled_for", "published_at", "publish_requested_at")
                      for p in await publishing.list_publications()]}


@router.post("/publications/{pid}/cancel")
async def publications_cancel(pid: str, payload: dict = Depends(require_jwt)):
    try:
        row = await publishing.cancel_publication(pid, _actor(payload))
    except publishing.GateError as e:
        raise HTTPException(400, str(e))
    if not row:
        raise HTTPException(404)
    return row


@router.post("/publications/{pid}/reconcile")
async def publications_reconcile(pid: str, payload: dict = Depends(require_jwt)):
    pub = await fetch_one("SELECT * FROM sm_publications WHERE id=?", (pid,))
    if not pub:
        raise HTTPException(404)
    if pub["state"] not in ("needs_manual_review", "publish_requested"):
        raise HTTPException(400, "ניתן לבצע התאמה רק לפרסום במצב לא ודאי")
    return await publishing.reconcile(pid, actor=_actor(payload))


class ResolveIn(BaseModel):
    outcome: Literal["published", "failed"]
    provider_media_id: str | None = None
    note: str | None = None


@router.post("/publications/{pid}/resolve")
async def publications_resolve(pid: str, body: ResolveIn, payload: dict = Depends(require_jwt)):
    try:
        return await publishing.manual_resolve(pid, body.outcome, _actor(payload), body.provider_media_id, body.note)
    except publishing.GateError as e:
        raise HTTPException(400, str(e))


# ── Calendar ───────────────────────────────────────────────────────────────

@router.get("/calendar")
async def calendar(days: int = Query(30, ge=7, le=90)):
    items = await content.list_items(include_demo=await _include_demo(), limit=500)
    scheduled = [_local(i, "scheduled_for") for i in items if i.get("scheduled_for")]
    return {"items": scheduled, "proposals": await propose_calendar(days), "content_mix": await get_setting("content_mix")}


# ── Instagram connection ───────────────────────────────────────────────────

SUPPORTED_FORMATS = [
    {"format": "image", "label": "פוסט תמונה", "api": True, "notes": "JPEG ≤8MB, יחס 4:5–1.91:1, alt text ≤1000"},
    {"format": "carousel", "label": "קרוסלה", "api": True, "notes": "2–20 פריטים, תמונות/וידאו"},
    {"format": "reel", "label": "רילס", "api": True, "notes": "MP4/MOV H.264, ≤300MB, 3s–15min, 9:16"},
    {"format": "story", "label": "סטורי", "api": "business_only", "notes": "חשבון עסקי בלבד; ללא מדבקות/לינקים דרך API"},
]


@router.get("/instagram/status")
async def instagram_status():
    provider = get_provider()
    acct = await provider.account()
    pub = await get_setting("publishing")
    out = {
        "provider_mode": provider.mode, "demo_mode": pub.get("demo_mode"), "account": acct,
        "token": publishing.token_status(acct) if provider.mode == "live" else {"ok": bool(acct), "label": "mock"},
        "login_path": "Instagram API with Facebook Login", "scopes": OAUTH_SCOPES,
        "permissions_status": "לא ניתן לאמת הרשאות ללא חיבור אמיתי" if provider.mode != "live" else "ראו token + publishing_limit",
        "supported_formats": SUPPORTED_FORMATS, "publishing_limit": None, "published_24h": None,
        "app_configured": bool(platform_cfg.meta_app_id),
        "media_base_url": scfg.media_base_url, "media_url_ttl_seconds": scfg.media_url_ttl_seconds,
    }
    if acct:
        out["published_24h"] = await publishing.published_last_24h(acct.get("ig_user_id"))
    if provider.mode == "live" and acct:
        try:
            live = await live_account_with_token()
            out["publishing_limit"] = await provider.publishing_limit(live["ig_user_id"], live["access_token"])
        except Exception as e:  # never expose token; show readable error
            out["publishing_limit_error"] = type(e).__name__
    return out


@router.post("/instagram/connect-url")
async def instagram_connect_url(payload: dict = Depends(require_jwt)):
    try:
        url = build_oauth_url()
    except GraphAPIError as e:
        raise HTTPException(400, str(e))
    await audit(_actor(payload), "instagram_connect_started", "instagram")
    return {"connect_url": url}


@router.get("/instagram/history")
async def instagram_history():
    rows = await fetch_all(
        "SELECT p.id, p.mode, p.state, p.container_id, p.provider_media_id, p.permalink, p.published_at, p.last_error, "
        "i.title, i.format FROM sm_publications p JOIN sm_content_items i ON i.id=p.content_item_id "
        "WHERE p.state IN ('published','failed','needs_manual_review') ORDER BY p.updated_at DESC LIMIT 100")
    return {"items": [_local(r, "published_at") for r in rows]}


# ── Inbound (comments / DMs) — draft-only ──────────────────────────────────

@router.get("/inbound")
async def inbound_list():
    rows = await fetch_all("SELECT * FROM sm_inbound_messages" + ("" if await _include_demo() else " WHERE is_demo=0")
                           + " ORDER BY received_at DESC LIMIT 200")
    return {"outbound_enabled": False, "permissions": "instagram_manage_comments / instagram_manage_messages לא מבוקשים ב-MVP",
            "items": rows}


class InboundIn(BaseModel):
    kind: Literal["comment", "dm"]
    author: str | None = None
    text: str
    provider_id: str | None = None


@router.post("/inbound", status_code=201)
async def inbound_add(body: InboundIn, payload: dict = Depends(require_jwt)):
    from security.injection_gate import gate
    from .db import new_id
    g = gate(body.text, body.kind)
    mid = new_id()
    await execute("INSERT INTO sm_inbound_messages (id, kind, provider_id, author, text, flagged, flag_reasons) VALUES (?,?,?,?,?,?,?)",
                  (mid, body.kind, body.provider_id, body.author, body.text, int(g.flagged), ",".join(g.flag_reasons) or None))
    return await fetch_one("SELECT * FROM sm_inbound_messages WHERE id=?", (mid,))


@router.post("/inbound/{mid}/draft-reply")
async def inbound_draft(mid: str):
    msg = await fetch_one("SELECT * FROM sm_inbound_messages WHERE id=?", (mid,))
    if not msg:
        raise HTTPException(404)
    out = await agents.draft_reply(msg)
    await execute("UPDATE sm_inbound_messages SET draft_reply=?, flagged=?, flag_reasons=? WHERE id=?",
                  (out.get("reply"), int(out.get("flagged", False)), ",".join(out.get("flag_reasons") or []) or None, mid))
    return {"llm_mode": llm.mode, "draft": out, "sent": False, "note": "תשובות יוצאות מושבתות — טיוטה בלבד"}


class InboundPatch(BaseModel):
    reply_status: Literal["draft_only", "approved_not_sent", "dismissed"]
    draft_reply: str | None = None


@router.patch("/inbound/{mid}")
async def inbound_patch(mid: str, body: InboundPatch):
    await execute("UPDATE sm_inbound_messages SET reply_status=?, draft_reply=COALESCE(?, draft_reply) WHERE id=?",
                  (body.reply_status, body.draft_reply, mid))
    row = await fetch_one("SELECT * FROM sm_inbound_messages WHERE id=?", (mid,))
    if not row:
        raise HTTPException(404)
    return row


# ── Metrics & reports ──────────────────────────────────────────────────────

@router.get("/metrics")
async def metrics_get():
    inc = await _include_demo()
    return {"provider_mode": get_provider().mode, "account": await metrics.latest_account_metrics(inc),
            "posts": await metrics.post_metrics(inc)}


class ManualMetric(BaseModel):
    scope: Literal["account", "post"] = "account"
    metric: str
    value: float
    content_item_id: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    note: str | None = None


@router.post("/metrics/manual", status_code=201)
async def metrics_manual(body: ManualMetric, payload: dict = Depends(require_jwt)):
    row = await metrics.record(body.scope, body.metric, body.value, "manual", body.content_item_id, None,
                               body.period_start, body.period_end, body.note)
    await audit(_actor(payload), "metric_manual", "metrics", row["id"], {"metric": body.metric})
    return row


@router.post("/metrics/refresh")
async def metrics_refresh():
    return await metrics.refresh_metrics()


@router.get("/reports")
async def reports_list():
    return {"items": await reports.list_reports()}


@router.get("/reports/{rid}")
async def reports_get(rid: str):
    r = await reports.get_report(rid)
    if not r:
        raise HTTPException(404)
    return r


@router.post("/reports/weekly", status_code=201)
async def reports_build(payload: dict = Depends(require_jwt)):
    r = await reports.build_weekly_report()
    await audit(_actor(payload), "report_built", "report", r["id"])
    return r


# ── Jobs / schedules / worker ──────────────────────────────────────────────

@router.get("/jobs")
async def jobs_list(status: str | None = None, limit: int = Query(100, le=500)):
    await jobs.ensure_schedules()
    return {"worker": await jobs.worker_status(), "schedules": await jobs.list_schedules(),
            "jobs": await jobs.list_jobs(limit, status), "labels": jobs.JOB_LABELS}


class JobIn(BaseModel):
    type: Literal["research", "ideas", "drafts", "planning", "weekly_report", "metrics", "token_check"]
    payload: dict = Field(default_factory=dict)
    run_now: bool = False


@router.post("/jobs", status_code=201)
async def jobs_create(body: JobIn, payload: dict = Depends(require_jwt)):
    job = await jobs.enqueue(body.type, body.payload)
    await audit(_actor(payload), "job_enqueued", "job", job["id"], {"type": body.type, "run_now": body.run_now})
    if body.run_now:
        claimed = await _claim_specific(job["id"])
        if claimed:
            job = await jobs.run_job(claimed, "api:" + _actor(payload))
    return job


@router.post("/jobs/{jid}/retry")
async def jobs_retry(jid: str, payload: dict = Depends(require_jwt)):
    job = await fetch_one("SELECT * FROM sm_jobs WHERE id=?", (jid,))
    if not job:
        raise HTTPException(404)
    if job["status"] not in ("failed", "skipped", "cancelled"):
        raise HTTPException(400, "ניתן להריץ מחדש רק ג'וב שנכשל/דולג")
    new = await jobs.enqueue(job["type"], json.loads(job["payload"] or "{}"))
    await audit(_actor(payload), "job_retried", "job", jid, {"new": new["id"]})
    return new


@router.patch("/schedules/{key}")
async def schedules_patch(key: str, body: dict, payload: dict = Depends(require_jwt)):
    try:
        row = await jobs.update_schedule(key, body)
    except ValueError as e:
        _err(e)
    if not row:
        raise HTTPException(404)
    await audit(_actor(payload), "schedule_updated", "schedule", key, body)
    return row


@router.post("/worker/tick")
async def worker_tick(payload: dict = Depends(require_jwt)):
    """Dev convenience: run one worker iteration inside the API process."""
    return await jobs.tick("api:" + _actor(payload))


@router.get("/audit")
async def audit_list(limit: int = Query(100, le=500)):
    return {"items": await fetch_all("SELECT * FROM sm_audit_log ORDER BY created_at DESC LIMIT ?", (limit,))}


# ── Leads ──────────────────────────────────────────────────────────────────

@router.get("/leads")
async def leads_list():
    return {"items": await leads.list_leads(include_demo=await _include_demo()), "statuses": leads.STATUSES}


class LeadIn(BaseModel):
    name: str
    handle: str | None = None
    lead_date: str | None = None
    source: str | None = None
    business_type: str | None = None
    need: str | None = None
    status: str | None = None
    next_action: str | None = None
    notes: str | None = None
    consent_note: str | None = None


@router.post("/leads", status_code=201)
async def leads_add(body: LeadIn, payload: dict = Depends(require_jwt)):
    try:
        return await leads.create_lead(body.model_dump(), _actor(payload))
    except ValueError as e:
        _err(e)


@router.patch("/leads/{lid}")
async def leads_patch(lid: str, body: dict, payload: dict = Depends(require_jwt)):
    try:
        row = await leads.update_lead(lid, body, _actor(payload))
    except ValueError as e:
        _err(e)
    if not row:
        raise HTTPException(404)
    return row


@router.delete("/leads/{lid}")
async def leads_delete(lid: str, payload: dict = Depends(require_jwt)):
    if not await leads.delete_lead(lid, _actor(payload)):
        raise HTTPException(404)
    return {"deleted": True}


class PurgeIn(BaseModel):
    days: int = Field(ge=1, le=3650)


@router.post("/leads/purge")
async def leads_purge(body: PurgeIn, payload: dict = Depends(require_jwt)):
    return {"deleted": await leads.purge_old_leads(body.days, _actor(payload))}


# ── Test hook (mock provider behaviour) — dev only ─────────────────────────

class MockBehaviour(BaseModel):
    behaviour: Literal["none", "timeout_on_publish", "retryable_error", "permanent_error", "container_error"]


@router.post("/dev/mock-behaviour")
async def dev_mock_behaviour(body: MockBehaviour):
    if not platform_cfg.dev_mode:
        raise HTTPException(403, "dev only")
    mock_provider().behaviour = None if body.behaviour == "none" else body.behaviour
    return {"behaviour": mock_provider().behaviour}

