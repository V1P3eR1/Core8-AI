"""Small async helpers over the shared aiosqlite connection factory."""

import datetime
import hashlib
import json
import uuid
from typing import Any
from zoneinfo import ZoneInfo

import aiosqlite

from database import get_db
from security.log_redact import redact

from .config import scfg

UTC = datetime.timezone.utc
LOCAL_TZ = ZoneInfo(scfg.timezone)


def new_id() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime.datetime:
    return datetime.datetime.now(UTC)


def utc_str(dt: datetime.datetime | None = None) -> str:
    """SQLite-friendly UTC string, 'YYYY-MM-DD HH:MM:SS'."""
    dt = dt or now_utc()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def parse_utc(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    v = value.strip().replace("T", " ")
    if v.endswith("Z"):
        v = v[:-1]
    try:
        dt = datetime.datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def local_to_utc(local_iso: str) -> str | None:
    """'2026-11-02T09:00' in Asia/Jerusalem -> UTC string. None if invalid."""
    try:
        dt = datetime.datetime.fromisoformat(local_iso.strip())
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return utc_str(dt)


def utc_to_local_iso(value: str | None) -> str | None:
    dt = parse_utc(value)
    return dt.astimezone(LOCAL_TZ).isoformat() if dt else None


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def jdump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def jload(text: str | None, default: Any = None) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default


async def fetch_all(sql: str, args: tuple = ()) -> list[dict]:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, args) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def fetch_one(sql: str, args: tuple = ()) -> dict | None:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, args) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def execute(sql: str, args: tuple = ()) -> int:
    """Run one statement, commit, return rowcount."""
    async with get_db() as db:
        cur = await db.execute(sql, args)
        await db.commit()
        return cur.rowcount


async def audit(actor: str, action: str, entity: str | None = None,
                entity_id: str | None = None, details: Any = None) -> None:
    await execute(
        "INSERT INTO sm_audit_log (id, actor, action, entity, entity_id, details) VALUES (?,?,?,?,?,?)",
        (new_id(), actor, action, entity, entity_id,
         redact(jdump(details), max_len=2000) if details is not None else None),
    )
