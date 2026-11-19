"""Jobs, schedules and the worker loop.

- sm_schedules: editable recurring jobs in Asia/Jerusalem local time
  (DST-aware via zoneinfo). next_run_at is stored in UTC.
- sm_jobs: one row per execution. Scheduled executions carry
  (schedule_key, run_at) which is UNIQUE, so two workers (or a restart) can
  never enqueue the same run twice.
- Claims are transactional UPDATEs guarded by status + lock expiry.
- Missed jobs: a pending job older than `missed_job_grace_minutes` is marked
  `skipped` (explicit, visible in the jobs screen) instead of running late.
- Heartbeat: the worker writes sm_settings.worker every tick; the API shows
  "worker offline" when it is stale.
"""

import asyncio
import datetime
import logging
import os
import socket
import traceback

from security.log_redact import redact

from .config import scfg
from .db import LOCAL_TZ, audit, execute, fetch_all, fetch_one, jdump, jload, new_id, now_utc, parse_utc, utc_str
from .settings import get_setting, set_setting

logger = logging.getLogger("core8.social.jobs")

DEFAULT_SCHEDULES: list[dict] = [
    {"key": "daily_research", "job_type": "research", "hour": 8, "minute": 30, "weekday": None, "label": "מחקר יומי"},
    {"key": "weekly_planning", "job_type": "planning", "hour": 9, "minute": 0, "weekday": 6, "label": "תכנון תוכן שבועי (ראשון)"},
    {"key": "weekly_report", "job_type": "weekly_report", "hour": 18, "minute": 0, "weekday": 3, "label": "דוח שבועי (חמישי)"},
    {"key": "daily_metrics", "job_type": "metrics", "hour": 7, "minute": 0, "weekday": None, "label": "משיכת מדדים יומית"},
    {"key": "daily_token_check", "job_type": "token_check", "hour": 7, "minute": 15, "weekday": None, "label": "בדיקת טוקן יומית"},
]
JOB_LABELS = {"research": "מחקר", "planning": "תכנון תוכן", "weekly_report": "דוח שבועי", "metrics": "מדדים",
              "token_check": "בדיקת טוקן", "drafts": "יצירת טיוטות", "ideas": "יצירת רעיונות", "publish": "פרסום"}


# ── Schedules ──────────────────────────────────────────────────────────────

def compute_next_run(hour: int, minute: int, weekday: int | None, after: datetime.datetime | None = None) -> str:
    """Next occurrence strictly after `after` (UTC) in Asia/Jerusalem, returned as a UTC string.
    Handles DST transitions because the comparison happens in wall-clock local time."""
    after = after or now_utc()
    local_after = after.astimezone(LOCAL_TZ)
    for d in range(0, 8):
        day = (local_after + datetime.timedelta(days=d)).date()
        if weekday is not None and day.weekday() != weekday:
            continue
        candidate = datetime.datetime(day.year, day.month, day.day, hour, minute, tzinfo=LOCAL_TZ)
        if candidate > local_after:
            return utc_str(candidate)
    # weekday only — guaranteed within 8 days; fallback for safety
    return utc_str(local_after + datetime.timedelta(days=7))


async def ensure_schedules() -> None:
    for s in DEFAULT_SCHEDULES:
        existing = await fetch_one("SELECT key FROM sm_schedules WHERE key=?", (s["key"],))
        if not existing:
            await execute(
                "INSERT INTO sm_schedules (key, job_type, hour, minute, weekday, enabled, next_run_at) VALUES (?,?,?,?,?,1,?)",
                (s["key"], s["job_type"], s["hour"], s["minute"], s["weekday"],
                 compute_next_run(s["hour"], s["minute"], s["weekday"])))


async def list_schedules() -> list[dict]:
    rows = await fetch_all("SELECT * FROM sm_schedules ORDER BY key")
    labels = {s["key"]: s["label"] for s in DEFAULT_SCHEDULES}
    for r in rows:
        r["label"] = labels.get(r["key"], r["key"])
        r["job_label"] = JOB_LABELS.get(r["job_type"], r["job_type"])
        for k in ("last_run_at", "next_run_at"):
            dt = parse_utc(r.get(k))
            r[k + "_local"] = dt.astimezone(LOCAL_TZ).isoformat() if dt else None
    return rows


async def update_schedule(key: str, patch: dict) -> dict | None:
    row = await fetch_one("SELECT * FROM sm_schedules WHERE key=?", (key,))
    if not row:
        return None
    hour = int(patch.get("hour", row["hour"]))
    minute = int(patch.get("minute", row["minute"]))
    weekday = patch.get("weekday", row["weekday"])
    weekday = None if weekday in (None, "", "null") else int(weekday)
    enabled = 1 if patch.get("enabled", row["enabled"]) else 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and (weekday is None or 0 <= weekday <= 6)):
        raise ValueError("שעה/דקה/יום לא תקינים")
    await execute("UPDATE sm_schedules SET hour=?, minute=?, weekday=?, enabled=?, next_run_at=?, updated_at=? WHERE key=?",
                  (hour, minute, weekday, enabled, compute_next_run(hour, minute, weekday), utc_str(), key))
    return (await list_schedules_map()).get(key)


async def list_schedules_map() -> dict:
    return {r["key"]: r for r in await list_schedules()}


# ── Job queue ──────────────────────────────────────────────────────────────

async def enqueue(job_type: str, payload: dict | None = None, run_at: str | None = None,
                  schedule_key: str | None = None, max_attempts: int = 3) -> dict | None:
    """Insert a job. For scheduled jobs the (schedule_key, run_at) unique index makes this idempotent."""
    jid = new_id()
    run_at = run_at or utc_str()
    try:
        await execute(
            "INSERT INTO sm_jobs (id, type, schedule_key, run_at, payload, max_attempts) VALUES (?,?,?,?,?,?)",
            (jid, job_type, schedule_key, run_at, jdump(payload or {}), max_attempts))
    except Exception as e:  # UNIQUE violation → already enqueued
        if "UNIQUE" in str(e).upper():
            return await fetch_one("SELECT * FROM sm_jobs WHERE schedule_key=? AND run_at=?", (schedule_key, run_at))
        raise
    return await fetch_one("SELECT * FROM sm_jobs WHERE id=?", (jid,))


async def list_jobs(limit: int = 100, status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM sm_jobs" + (" WHERE status=?" if status else "") + " ORDER BY run_at DESC LIMIT ?"
    rows = await fetch_all(sql, ((status, limit) if status else (limit,)))
    for r in rows:
        r["payload"] = jload(r["payload"], {})
        r["result"] = jload(r["result"], None)
        r["label"] = JOB_LABELS.get(r["type"], r["type"])
        dt = parse_utc(r["run_at"])
        r["run_at_local"] = dt.astimezone(LOCAL_TZ).isoformat() if dt else None
    return rows


async def claim_due_jobs(worker_id: str, lock_seconds: int, limit: int = 3) -> list[dict]:
    now = utc_str()
    lock_until = utc_str(now_utc() + datetime.timedelta(seconds=lock_seconds))
    grace = utc_str(now_utc() - datetime.timedelta(minutes=scfg.missed_job_grace_minutes))
    # Explicit missed-job behaviour: too old → skipped, never run late.
    n = await execute("UPDATE sm_jobs SET status='skipped', error='missed: run_at older than grace window', "
                      "finished_at=? WHERE status='pending' AND run_at < ? AND schedule_key IS NOT NULL",
                      (now, grace))
    if n:
        logger.warning("Marked %d missed scheduled job(s) as skipped", n)
    rows = await fetch_all(
        "SELECT id FROM sm_jobs WHERE run_at <= ? AND (status='pending' OR (status='running' AND lock_expires_at < ?)) "
        "ORDER BY run_at LIMIT ?", (now, now, limit))
    claimed = []
    for r in rows:
        ok = await execute(
            "UPDATE sm_jobs SET status='running', claimed_by=?, claimed_at=?, lock_expires_at=?, started_at=?, "
            "attempts=attempts+1 WHERE id=? AND (status='pending' OR (status='running' AND lock_expires_at < ?))",
            (worker_id, now, lock_until, now, r["id"], now))
        if ok == 1:
            claimed.append(await fetch_one("SELECT * FROM sm_jobs WHERE id=?", (r["id"],)))
    return claimed


async def _finish(job: dict, status: str, result=None, error: str | None = None) -> None:
    await execute("UPDATE sm_jobs SET status=?, result=?, error=?, finished_at=?, lock_expires_at=NULL WHERE id=?",
                  (status, jdump(result) if result is not None else None, redact(error, 1000) if error else None,
                   utc_str(), job["id"]))


async def run_job(job: dict, worker_id: str = "worker") -> dict:
    """Dispatch one claimed job. Failures are recorded; retryable ones re-queue with backoff."""
    payload = jload(job["payload"], {}) or {}
    try:
        result = await HANDLERS[job["type"]](payload, job["id"])
        await _finish(job, "succeeded", result)
        if job.get("schedule_key"):
            await execute("UPDATE sm_schedules SET last_run_at=? WHERE key=?", (utc_str(), job["schedule_key"]))
    except KeyError:
        await _finish(job, "failed", error=f"unknown job type {job['type']}")
    except Exception as e:
        err = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}"
        logger.error("job %s (%s) failed: %s", job["id"], job["type"], redact(str(e), 300))
        if job["attempts"] < job["max_attempts"]:
            next_at = utc_str(now_utc() + datetime.timedelta(minutes=5 * job["attempts"]))
            await execute("UPDATE sm_jobs SET status='pending', run_at=?, error=?, lock_expires_at=NULL, "
                          "schedule_key=NULL WHERE id=?", (next_at, redact(err, 1000), job["id"]))
        else:
            await _finish(job, "failed", error=err)
            from .providers.notify import notifier
            await notifier.send("job_failed", f"ג'וב נכשל סופית: {JOB_LABELS.get(job['type'], job['type'])}",
                                {"job_id": job["id"]})
    row = await fetch_one("SELECT * FROM sm_jobs WHERE id=?", (job["id"],))
    row["payload"] = jload(row["payload"], {})
    row["result"] = jload(row["result"], None)
    return row


# ── Handlers ───────────────────────────────────────────────────────────────

async def _h_research(payload: dict, job_id: str) -> dict:
    from .agents import run_research
    return await run_research(job_id=job_id, max_per_feed=int(payload.get("max_per_feed", 8)))


async def _h_ideas(payload: dict, job_id: str) -> dict:
    from .agents import generate_ideas
    ideas = await generate_ideas(count=int(payload.get("count", 20)), job_id=job_id,
                                 is_demo=bool(payload.get("is_demo")))
    return {"created": len(ideas), "ids": [i["id"] for i in ideas]}


async def _h_drafts(payload: dict, job_id: str) -> dict:
    from .agents import draft_package
    from .content import get_idea
    out = []
    for iid in payload.get("idea_ids", []):
        idea = await get_idea(iid)
        if idea:
            item = await draft_package(idea, payload.get("format"), job_id=job_id)
            out.append(item["id"])
    return {"items": out}


async def _h_planning(payload: dict, job_id: str) -> dict:
    """Weekly planning: top up ideas, draft shortlisted ideas, propose calendar slots, run auto-mode gates."""
    from .agents import draft_package, generate_ideas
    from .content import list_ideas
    from .planner import propose_calendar
    from .publishing import auto_schedule_candidates
    new_ideas = []
    if len(await list_ideas(include_demo=False, status="new")) < 5:
        new_ideas = await generate_ideas(count=10, job_id=job_id)
    drafted = []
    for idea in await list_ideas(include_demo=False, status="shortlisted"):
        item = await draft_package(idea, job_id=job_id)
        drafted.append(item["id"])
    calendar = await propose_calendar(days=30)
    auto = await auto_schedule_candidates()
    return {"new_ideas": len(new_ideas), "drafted": drafted, "calendar_slots": len(calendar),
            "auto_scheduled": [p["id"] for p in auto]}


async def _h_weekly_report(payload: dict, job_id: str) -> dict:
    from .reports import build_weekly_report
    rep = await build_weekly_report()
    return {"report_id": rep["id"]}


async def _h_metrics(payload: dict, job_id: str) -> dict:
    from .metrics import refresh_metrics
    return await refresh_metrics()


async def _h_token_check(payload: dict, job_id: str) -> dict:
    from .providers.instagram import get_provider
    from .providers.notify import notifier
    from .publishing import token_status
    acct = await get_provider().account()
    ts = token_status(acct)
    if not ts["ok"] or ts.get("reason") == "expiring":
        await notifier.send("token_warning", ts["label"], {"expires_at": ts.get("expires_at")})
    return ts


HANDLERS = {
    "research": _h_research, "ideas": _h_ideas, "drafts": _h_drafts, "planning": _h_planning,
    "weekly_report": _h_weekly_report, "metrics": _h_metrics, "token_check": _h_token_check,
}


# ── Worker loop ────────────────────────────────────────────────────────────

def worker_identity() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


async def heartbeat(worker_id: str, note: str | None = None) -> None:
    await set_setting("worker", {"worker_id": worker_id, "heartbeat_at": utc_str(), "note": note,
                                 "poll_seconds": scfg.worker_poll_seconds})


async def worker_status() -> dict:
    w = await get_setting("worker")
    hb = parse_utc(w.get("heartbeat_at")) if w else None
    stale_after = max(60, int(scfg.worker_poll_seconds * 3))
    online = bool(hb and (now_utc() - hb).total_seconds() < stale_after)
    return {"online": online, "worker_id": w.get("worker_id") if w else None,
            "heartbeat_at": w.get("heartbeat_at") if w else None, "stale_after_seconds": stale_after,
            "inprocess": scfg.worker_inprocess}


async def tick(worker_id: str) -> dict:
    """One scheduler/worker iteration. Safe to call concurrently from several workers."""
    from .publishing import claim_due_publications, run_publication
    await ensure_schedules()
    now = utc_str()
    enq = 0
    for s in await fetch_all("SELECT * FROM sm_schedules WHERE enabled=1 AND next_run_at <= ?", (now,)):
        job = await enqueue(s["job_type"], {}, run_at=s["next_run_at"], schedule_key=s["key"])
        enq += int(bool(job))
        await execute("UPDATE sm_schedules SET next_run_at=? WHERE key=? AND next_run_at=?",
                      (compute_next_run(s["hour"], s["minute"], s["weekday"]), s["key"], s["next_run_at"]))
    ran = []
    for job in await claim_due_jobs(worker_id, scfg.job_lock_seconds):
        ran.append((await run_job(job, worker_id))["status"])
    pubs = []
    for pub in await claim_due_publications(worker_id, scfg.job_lock_seconds):
        pubs.append((await run_publication(pub, worker_id))["state"])
    if not worker_id.startswith("api:"):   # an API-triggered tick is not a running worker
        await heartbeat(worker_id)
    return {"enqueued": enq, "jobs": ran, "publications": pubs}


async def worker_loop(is_stopped=lambda: False, worker_id: str | None = None) -> None:
    worker_id = worker_id or worker_identity()
    logger.info("Social worker %s started (poll %ss)", worker_id, scfg.worker_poll_seconds)
    await audit("system", "worker_started", "worker", worker_id)
    while not is_stopped():
        try:
            await tick(worker_id)
        except Exception as e:
            logger.error("worker tick failed: %s", redact(str(e), 300))
        await asyncio.sleep(scfg.worker_poll_seconds)
