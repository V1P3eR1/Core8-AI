"""Lead management tools — backed by the leads SQLite table."""

import uuid
from database import get_db
from tools.registry import ToolDef, registry

_VALID_STATUSES = {"new", "contacted", "qualified", "proposal", "won", "lost"}


async def create_lead(name: str, email: str = "", company: str = "",
                      status: str = "new", source: str = "", notes: str = "") -> dict:
    if status not in _VALID_STATUSES:
        return {"error": f"Invalid status '{status}'. Valid: {sorted(_VALID_STATUSES)}"}
    lead_id = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            """INSERT INTO leads (id, name, email, company, status, source, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (lead_id, name, email, company, status, source, notes),
        )
        await db.commit()
    return {"id": lead_id, "name": name, "email": email, "company": company,
            "status": status, "source": source}


async def list_leads(status: str = "", limit: int = 50) -> list[dict]:
    async with get_db() as db:
        import aiosqlite
        db.row_factory = aiosqlite.Row
        if status and status in _VALID_STATUSES:
            async with db.execute(
                "SELECT * FROM leads WHERE status=? ORDER BY created_at DESC LIMIT ?",
                (status, min(limit, 200)),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM leads ORDER BY created_at DESC LIMIT ?",
                (min(limit, 200),),
            ) as cur:
                rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def update_lead(lead_id: str, name: str = "", email: str = "", company: str = "",
                      status: str = "", source: str = "") -> dict:
    updates, params = [], []
    if name:    updates.append("name=?");    params.append(name)
    if email:   updates.append("email=?");   params.append(email)
    if company: updates.append("company=?"); params.append(company)
    if status:
        if status not in _VALID_STATUSES:
            return {"error": f"Invalid status '{status}'."}
        updates.append("status=?"); params.append(status)
    if source:  updates.append("source=?");  params.append(source)
    if not updates:
        return {"error": "No fields to update"}
    updates.append("updated_at=datetime('now')")
    params.append(lead_id)
    async with get_db() as db:
        await db.execute(
            f"UPDATE leads SET {', '.join(updates)} WHERE id=?", params
        )
        await db.commit()
    return {"updated": lead_id}


async def add_note(lead_id: str, note: str) -> dict:
    async with get_db() as db:
        import aiosqlite
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT notes FROM leads WHERE id=?", (lead_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            return {"error": f"Lead {lead_id} not found"}
        existing = row["notes"] or ""
        import datetime
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        new_notes = f"{existing}\n[{timestamp}] {note}".strip()
        await db.execute(
            "UPDATE leads SET notes=?, updated_at=datetime('now') WHERE id=?",
            (new_notes, lead_id),
        )
        await db.commit()
    return {"lead_id": lead_id, "note_added": note}


async def search_leads(query: str) -> list[dict]:
    like = f"%{query}%"
    async with get_db() as db:
        import aiosqlite
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM leads
               WHERE name LIKE ? OR email LIKE ? OR company LIKE ? OR notes LIKE ?
               ORDER BY updated_at DESC LIMIT 50""",
            (like, like, like, like),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_lead(lead_id: str) -> dict:
    async with get_db() as db:
        import aiosqlite
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        return {"error": f"Lead {lead_id} not found"}
    return dict(row)


def register_leads_tools():
    registry.register(ToolDef(
        name="create_lead",
        description="Create a new sales lead in the CRM.",
        input_schema={
            "type": "object",
            "properties": {
                "name":    {"type": "string", "description": "Full name of the lead"},
                "email":   {"type": "string", "description": "Email address"},
                "company": {"type": "string", "description": "Company name"},
                "status":  {"type": "string", "description": "new|contacted|qualified|proposal|won|lost"},
                "source":  {"type": "string", "description": "Lead source (e.g. LinkedIn, referral)"},
                "notes":   {"type": "string", "description": "Initial notes"},
            },
            "required": ["name"],
        },
        handler=create_lead,
    ))
    registry.register(ToolDef(
        name="list_leads",
        description="List all leads, optionally filtered by status.",
        input_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status (optional)"},
                "limit":  {"type": "integer", "description": "Max results (default 50)"},
            },
        },
        handler=list_leads,
    ))
    registry.register(ToolDef(
        name="update_lead",
        description="Update fields on an existing lead.",
        input_schema={
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
                "name":    {"type": "string"},
                "email":   {"type": "string"},
                "company": {"type": "string"},
                "status":  {"type": "string"},
                "source":  {"type": "string"},
            },
            "required": ["lead_id"],
        },
        handler=update_lead,
    ))
    registry.register(ToolDef(
        name="add_note",
        description="Append a timestamped note to a lead.",
        input_schema={
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
                "note":    {"type": "string"},
            },
            "required": ["lead_id", "note"],
        },
        handler=add_note,
    ))
    registry.register(ToolDef(
        name="search_leads",
        description="Search leads by name, email, company, or notes.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
        handler=search_leads,
    ))
    registry.register(ToolDef(
        name="get_lead",
        description="Get full details of a single lead by ID.",
        input_schema={
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
            },
            "required": ["lead_id"],
        },
        handler=get_lead,
    ))
