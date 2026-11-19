"""Lead tracker — manual or legitimately received leads only. No outbound automation."""

from .db import audit, execute, fetch_all, fetch_one, new_id, utc_str

LEAD_FIELDS = ("name", "handle", "lead_date", "source", "business_type", "need", "status", "next_action", "notes",
               "consent_note")
STATUSES = ("new", "contacted", "qualified", "proposal", "won", "lost", "archived")


async def list_leads(include_demo: bool = True) -> list[dict]:
    sql = "SELECT * FROM sm_leads" + ("" if include_demo else " WHERE is_demo=0") + " ORDER BY created_at DESC"
    return await fetch_all(sql)


async def create_lead(data: dict, actor: str) -> dict:
    if not (data.get("name") or "").strip():
        raise ValueError("שם או מזהה חשבון נדרש")
    if data.get("status") and data["status"] not in STATUSES:
        raise ValueError("סטטוס לא תקין")
    lid = new_id()
    vals = [data.get(k) for k in LEAD_FIELDS]
    vals[6] = vals[6] or "new"
    await execute(f"INSERT INTO sm_leads (id, {', '.join(LEAD_FIELDS)}, is_demo) VALUES (?,{','.join('?' * len(LEAD_FIELDS))},0)",
                  (lid, *vals))
    await audit(actor, "lead_created", "lead", lid)
    return await fetch_one("SELECT * FROM sm_leads WHERE id=?", (lid,))


async def update_lead(lid: str, patch: dict, actor: str) -> dict | None:
    fields = {k: v for k, v in patch.items() if k in LEAD_FIELDS}
    if fields.get("status") and fields["status"] not in STATUSES:
        raise ValueError("סטטוס לא תקין")
    if fields:
        sets = ", ".join(f"{k}=?" for k in fields) + ", updated_at=?"
        await execute(f"UPDATE sm_leads SET {sets} WHERE id=?", (*fields.values(), utc_str(), lid))
        await audit(actor, "lead_updated", "lead", lid, {"fields": list(fields)})
    return await fetch_one("SELECT * FROM sm_leads WHERE id=?", (lid,))


async def delete_lead(lid: str, actor: str) -> bool:
    n = await execute("DELETE FROM sm_leads WHERE id=?", (lid,))
    if n:
        await audit(actor, "lead_deleted", "lead", lid)
    return bool(n)


async def purge_old_leads(days: int, actor: str) -> int:
    """Retention control: delete archived/lost leads older than N days."""
    n = await execute("DELETE FROM sm_leads WHERE status IN ('archived','lost') AND updated_at < datetime('now', ?)",
                      (f"-{int(days)} days",))
    await audit(actor, "leads_purged", "lead", None, {"days": days, "deleted": n})
    return n
