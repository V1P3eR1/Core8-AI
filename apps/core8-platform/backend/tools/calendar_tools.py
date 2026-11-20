"""Calendar / scheduling tools — backed by the events SQLite table."""

import uuid
import datetime
import aiosqlite
from database import get_db
from tenancy import current_tenant
from tools.registry import ToolDef, registry


def _parse_dt(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s)


async def create_event(title: str, start_time: str, end_time: str,
                       description: str = "", attendees: str = "") -> dict:
    try:
        s, e = _parse_dt(start_time), _parse_dt(end_time)
    except ValueError as exc:
        return {"error": f"Invalid datetime: {exc}. Use ISO 8601 (e.g. 2026-05-17T09:00:00)."}
    if e <= s:
        return {"error": "end_time must be after start_time"}

    event_id = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            """INSERT INTO events (tenant_id, id, title, start_time, end_time, description, attendees)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (current_tenant(), event_id, title, start_time, end_time, description, attendees),
        )
        await db.commit()
    return {"id": event_id, "title": title, "start_time": start_time, "end_time": end_time}


async def list_events(from_date: str = "", to_date: str = "", limit: int = 50) -> list[dict]:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        if from_date and to_date:
            async with db.execute(
                "SELECT * FROM events WHERE tenant_id=? AND start_time >= ? AND start_time <= ? "
                "ORDER BY start_time LIMIT ?",
                (current_tenant(), from_date, to_date, min(limit, 200)),
            ) as cur:
                rows = await cur.fetchall()
        elif from_date:
            async with db.execute(
                "SELECT * FROM events WHERE tenant_id=? AND start_time >= ? ORDER BY start_time LIMIT ?",
                (current_tenant(), from_date, min(limit, 200)),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM events WHERE tenant_id=? ORDER BY start_time LIMIT ?",
                (current_tenant(), min(limit, 200)),
            ) as cur:
                rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def find_free_slot(date: str, duration_minutes: int = 30,
                         work_start: str = "09:00", work_end: str = "18:00") -> dict:
    """Find the first available slot of given duration on the specified date."""
    try:
        day = datetime.date.fromisoformat(date)
    except ValueError:
        return {"error": f"Invalid date '{date}'. Use YYYY-MM-DD."}

    ws_h, ws_m = map(int, work_start.split(":"))
    we_h, we_m = map(int, work_end.split(":"))
    day_start = datetime.datetime(day.year, day.month, day.day, ws_h, ws_m)
    day_end   = datetime.datetime(day.year, day.month, day.day, we_h, we_m)
    duration  = datetime.timedelta(minutes=duration_minutes)

    # Fetch busy blocks for the day
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT start_time, end_time FROM events WHERE tenant_id=? AND start_time >= ? "
            "AND start_time < ? ORDER BY start_time",
            (current_tenant(), day_start.isoformat(), day_end.isoformat()),
        ) as cur:
            rows = await cur.fetchall()

    busy = [(_parse_dt(r["start_time"]), _parse_dt(r["end_time"])) for r in rows]

    # Walk from day_start, skip busy blocks
    cursor = day_start
    for b_start, b_end in busy:
        if cursor + duration <= b_start:
            return {"free_slot": {"start": cursor.isoformat(), "end": (cursor + duration).isoformat()}}
        if cursor < b_end:
            cursor = b_end

    if cursor + duration <= day_end:
        return {"free_slot": {"start": cursor.isoformat(), "end": (cursor + duration).isoformat()}}

    return {"free_slot": None, "message": f"No {duration_minutes}-min slot available on {date}"}


async def update_event(event_id: str, title: str = "", start_time: str = "",
                       end_time: str = "", description: str = "", attendees: str = "") -> dict:
    updates, params = [], []
    if title:       updates.append("title=?");       params.append(title)
    if start_time:  updates.append("start_time=?");  params.append(start_time)
    if end_time:    updates.append("end_time=?");    params.append(end_time)
    if description: updates.append("description=?"); params.append(description)
    if attendees:   updates.append("attendees=?");   params.append(attendees)
    if not updates:
        return {"error": "No fields to update"}
    params += [current_tenant(), event_id]
    async with get_db() as db:
        cur = await db.execute(f"UPDATE events SET {', '.join(updates)} WHERE tenant_id=? AND id=?", params)
        await db.commit()
    if cur.rowcount == 0:
        return {"error": f"Event {event_id} not found"}
    return {"updated": event_id}


async def delete_event(event_id: str) -> dict:
    async with get_db() as db:
        cur = await db.execute("DELETE FROM events WHERE tenant_id=? AND id=?", (current_tenant(), event_id))
        await db.commit()
    if cur.rowcount == 0:
        return {"error": f"Event {event_id} not found"}
    return {"deleted": event_id}


def register_calendar_tools():
    registry.register(ToolDef(
        name="create_event",
        description="Create a new calendar event.",
        input_schema={
            "type": "object",
            "properties": {
                "title":       {"type": "string"},
                "start_time":  {"type": "string", "description": "ISO 8601 datetime"},
                "end_time":    {"type": "string", "description": "ISO 8601 datetime"},
                "description": {"type": "string"},
                "attendees":   {"type": "string", "description": "Comma-separated names or emails"},
            },
            "required": ["title", "start_time", "end_time"],
        },
        handler=create_event,
    ))
    registry.register(ToolDef(
        name="list_events",
        description="List calendar events, optionally filtered by date range.",
        input_schema={
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "ISO 8601 start filter"},
                "to_date":   {"type": "string", "description": "ISO 8601 end filter"},
                "limit":     {"type": "integer"},
            },
        },
        handler=list_events,
    ))
    registry.register(ToolDef(
        name="find_free_slot",
        description="Find the first available time slot of a given duration on a date.",
        input_schema={
            "type": "object",
            "properties": {
                "date":             {"type": "string", "description": "YYYY-MM-DD"},
                "duration_minutes": {"type": "integer", "description": "Duration in minutes (default 30)"},
                "work_start":       {"type": "string", "description": "HH:MM working hours start (default 09:00)"},
                "work_end":         {"type": "string", "description": "HH:MM working hours end (default 18:00)"},
            },
            "required": ["date"],
        },
        handler=find_free_slot,
    ))
    registry.register(ToolDef(
        name="update_event",
        description="Update fields on an existing calendar event.",
        input_schema={
            "type": "object",
            "properties": {
                "event_id":    {"type": "string"},
                "title":       {"type": "string"},
                "start_time":  {"type": "string"},
                "end_time":    {"type": "string"},
                "description": {"type": "string"},
                "attendees":   {"type": "string"},
            },
            "required": ["event_id"],
        },
        handler=update_event,
    ))
    registry.register(ToolDef(
        name="delete_event",
        description="Delete a calendar event by ID.",
        input_schema={
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
            },
            "required": ["event_id"],
        },
        handler=delete_event,
    ))
