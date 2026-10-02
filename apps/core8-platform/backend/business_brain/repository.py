"""Tenant-scoped data access for the Business Brain.

All reads and writes of tenant data go through BrainRepository, which is bound to one
tenant_id at construction and adds it to every statement. Nothing in this module accepts a
tenant_id per call, so a caller cannot accidentally query another tenant's rows.
"""

import json
import uuid
from contextlib import asynccontextmanager

import aiosqlite

import database
from business_brain.schema import SENSITIVITY_LEVELS


@asynccontextmanager
async def _conn():
    async with database.get_db() as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        yield db


def _new_id() -> str:
    return str(uuid.uuid4())


def stricter(a: str, b: str) -> str:
    return a if SENSITIVITY_LEVELS.index(a) >= SENSITIVITY_LEVELS.index(b) else b


def _fact_row(row) -> dict:
    d = dict(row)
    d["value"] = json.loads(d.pop("value_json"))
    return d


# ── Tenant directory (not tenant-scoped by nature) ───────────────────────────

async def create_tenant(name: str, created_by: str, owner_user_ids: list[str] = ()) -> dict:
    """Create a tenant. Each user in owner_user_ids gets an explicit 'owner' membership."""
    tenant_id = _new_id()
    async with _conn() as db:
        await db.execute(
            "INSERT INTO tenants (id, name, created_by) VALUES (?,?,?)", (tenant_id, name, created_by)
        )
        for uid in dict.fromkeys(owner_user_ids):
            await db.execute(
                "INSERT INTO tenant_members (tenant_id, user_id, role, granted_by) VALUES (?,?, 'owner', ?)",
                (tenant_id, uid, created_by),
            )
        await db.commit()
    return {"id": tenant_id, "name": name}


async def list_tenants_for_user(user_id: str) -> list[dict]:
    """Tenants the user is an explicit member of."""
    async with _conn() as db:
        async with db.execute(
            """SELECT t.id, t.name, t.created_at, m.role FROM tenants t
               JOIN tenant_members m ON m.tenant_id = t.id
               WHERE m.user_id = ? ORDER BY t.created_at""",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def tenant_directory() -> list[dict]:
    """Names only, for platform admins to manage clients. Contains no Brain data."""
    async with _conn() as db:
        async with db.execute(
            """SELECT t.id, t.name, t.created_at,
                      (SELECT COUNT(*) FROM tenant_members m WHERE m.tenant_id = t.id) AS member_count
               FROM tenants t ORDER BY t.created_at"""
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_membership_role(tenant_id: str, user_id: str) -> str | None:
    async with _conn() as db:
        async with db.execute(
            "SELECT role FROM tenant_members WHERE tenant_id = ? AND user_id = ?", (tenant_id, user_id)
        ) as cur:
            row = await cur.fetchone()
    return row["role"] if row else None


async def tenant_exists(tenant_id: str) -> bool:
    async with _conn() as db:
        async with db.execute("SELECT 1 FROM tenants WHERE id = ?", (tenant_id,)) as cur:
            return await cur.fetchone() is not None


# ── Tenant-scoped repository ─────────────────────────────────────────────────

class BrainRepository:
    def __init__(self, tenant_id: str):
        if not tenant_id:
            raise ValueError("tenant_id is required")
        self.tenant_id = tenant_id

    # Tenant & members
    async def get_tenant(self) -> dict | None:
        async with _conn() as db:
            async with db.execute(
                "SELECT id, name, created_at FROM tenants WHERE id = ?", (self.tenant_id,)
            ) as cur:
                row = await cur.fetchone()
        return dict(row) if row else None

    async def set_member(self, user_id: str, role: str, granted_by: str) -> None:
        async with _conn() as db:
            await db.execute(
                """INSERT INTO tenant_members (tenant_id, user_id, role, granted_by) VALUES (?,?,?,?)
                   ON CONFLICT(tenant_id, user_id) DO UPDATE SET
                     role = excluded.role, granted_by = excluded.granted_by""",
                (self.tenant_id, user_id, role, granted_by),
            )
            await db.commit()

    async def list_members(self) -> list[dict]:
        async with _conn() as db:
            async with db.execute(
                """SELECT m.user_id, u.email, m.role, m.granted_by, m.created_at
                   FROM tenant_members m JOIN users u ON u.id = m.user_id
                   WHERE m.tenant_id = ? ORDER BY m.created_at""",
                (self.tenant_id,),
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def count_owners(self) -> int:
        async with _conn() as db:
            async with db.execute(
                "SELECT COUNT(*) FROM tenant_members WHERE tenant_id = ? AND role = 'owner'", (self.tenant_id,)
            ) as cur:
                return (await cur.fetchone())[0]

    async def get_member_role(self, user_id: str) -> str | None:
        return await get_membership_role(self.tenant_id, user_id)

    async def remove_member(self, user_id: str) -> None:
        async with _conn() as db:
            await db.execute(
                "DELETE FROM tenant_members WHERE tenant_id = ? AND user_id = ?", (self.tenant_id, user_id)
            )
            await db.commit()

    # Facts
    async def upsert_fact(
        self, *, fact_key: str, category: str, domain: str, value, sensitivity: str,
        source_type: str, source_ref: str | None, created_by: str, confidence: float = 1.0,
    ) -> tuple[dict, bool]:
        """Write a fact. Same value → no-op; different value → new version. Returns (fact, changed)."""
        value_json = json.dumps(value, ensure_ascii=False, sort_keys=True)
        async with _conn() as db:
            async with db.execute(
                """SELECT * FROM brain_facts WHERE tenant_id = ? AND fact_key = ? AND status = 'active'""",
                (self.tenant_id, fact_key),
            ) as cur:
                current = await cur.fetchone()
            if current and current["value_json"] == value_json and current["category"] == category:
                if stricter(current["sensitivity"], sensitivity) != current["sensitivity"]:
                    await db.execute(
                        "UPDATE brain_facts SET sensitivity = ? WHERE tenant_id = ? AND id = ?",
                        (sensitivity, self.tenant_id, current["id"]),
                    )
                    await db.commit()
                    return await self.get_fact(current["id"]), False
                return _fact_row(current), False

            async with db.execute(
                "SELECT COALESCE(MAX(version), 0) FROM brain_facts WHERE tenant_id = ? AND fact_key = ?",
                (self.tenant_id, fact_key),
            ) as cur:
                version = (await cur.fetchone())[0] + 1
            fact_id = _new_id()
            if current:
                await db.execute(
                    "UPDATE brain_facts SET status = 'superseded' WHERE tenant_id = ? AND id = ?",
                    (self.tenant_id, current["id"]),
                )
                # Never loosen sensitivity across versions.
                sensitivity = stricter(current["sensitivity"], sensitivity)
            await db.execute(
                """INSERT INTO brain_facts
                   (id, tenant_id, fact_key, version, category, domain, value_json, sensitivity,
                    status, source_type, source_ref, confidence, created_by, supersedes_id)
                   VALUES (?,?,?,?,?,?,?,?, 'active', ?,?,?,?,?)""",
                (fact_id, self.tenant_id, fact_key, version, category, domain, value_json, sensitivity,
                 source_type, source_ref, confidence, created_by, current["id"] if current else None),
            )
            await db.commit()
        return await self.get_fact(fact_id), True

    async def retract_fact(self, fact_key: str) -> None:
        async with _conn() as db:
            await db.execute(
                "UPDATE brain_facts SET status = 'retracted' WHERE tenant_id = ? AND fact_key = ? AND status = 'active'",
                (self.tenant_id, fact_key),
            )
            await db.commit()

    async def has_active_fact(self, fact_key: str) -> bool:
        async with _conn() as db:
            async with db.execute(
                "SELECT 1 FROM brain_facts WHERE tenant_id = ? AND fact_key = ? AND status = 'active'",
                (self.tenant_id, fact_key),
            ) as cur:
                return await cur.fetchone() is not None

    async def get_fact(self, fact_id: str) -> dict | None:
        async with _conn() as db:
            async with db.execute(
                "SELECT * FROM brain_facts WHERE tenant_id = ? AND id = ?", (self.tenant_id, fact_id)
            ) as cur:
                row = await cur.fetchone()
        return _fact_row(row) if row else None

    async def list_facts(
        self, *, category: str | None = None, domain: str | None = None,
        categories: list[str] | None = None, domains: list[str] | None = None,
        max_sensitivity: str | None = None,
    ) -> list[dict]:
        sql = "SELECT * FROM brain_facts WHERE tenant_id = ? AND status = 'active'"
        args: list = [self.tenant_id]
        if category:
            sql += " AND category = ?"
            args.append(category)
        if domain:
            sql += " AND domain = ?"
            args.append(domain)
        if categories is not None:
            sql += f" AND category IN ({','.join('?' * len(categories)) or 'NULL'})"
            args.extend(categories)
        if domains is not None:
            sql += f" AND domain IN ({','.join('?' * len(domains)) or 'NULL'})"
            args.extend(domains)
        if max_sensitivity is not None:
            allowed = SENSITIVITY_LEVELS[: SENSITIVITY_LEVELS.index(max_sensitivity) + 1]
            sql += f" AND sensitivity IN ({','.join('?' * len(allowed))})"
            args.extend(allowed)
        sql += " ORDER BY domain, category, fact_key"
        async with _conn() as db:
            async with db.execute(sql, args) as cur:
                return [_fact_row(r) for r in await cur.fetchall()]

    async def fact_history(self, fact_id: str) -> list[dict]:
        fact = await self.get_fact(fact_id)
        if not fact:
            return []
        async with _conn() as db:
            async with db.execute(
                "SELECT * FROM brain_facts WHERE tenant_id = ? AND fact_key = ? ORDER BY version",
                (self.tenant_id, fact["fact_key"]),
            ) as cur:
                return [_fact_row(r) for r in await cur.fetchall()]

    async def tighten_domain_sensitivity(self, domain: str, level: str) -> int:
        """Raise sensitivity of active facts in a domain to at least `level`. Never lowers it."""
        looser = SENSITIVITY_LEVELS[: SENSITIVITY_LEVELS.index(level)]
        if not looser:
            return 0
        async with _conn() as db:
            cur = await db.execute(
                f"""UPDATE brain_facts SET sensitivity = ?
                    WHERE tenant_id = ? AND domain = ? AND status = 'active'
                    AND sensitivity IN ({','.join('?' * len(looser))})""",
                (level, self.tenant_id, domain, *looser),
            )
            await db.commit()
            return cur.rowcount

    # Assessments
    async def create_assessment(self, questionnaire_version: str, created_by: str) -> dict:
        aid = _new_id()
        async with _conn() as db:
            await db.execute(
                """INSERT INTO discovery_assessments (id, tenant_id, questionnaire_version, created_by)
                   VALUES (?,?,?,?)""",
                (aid, self.tenant_id, questionnaire_version, created_by),
            )
            await db.commit()
        return await self.get_assessment(aid)

    async def get_assessment(self, assessment_id: str) -> dict | None:
        async with _conn() as db:
            async with db.execute(
                "SELECT * FROM discovery_assessments WHERE tenant_id = ? AND id = ?",
                (self.tenant_id, assessment_id),
            ) as cur:
                row = await cur.fetchone()
        return dict(row) if row else None

    async def get_answers(self, assessment_id: str) -> dict:
        async with _conn() as db:
            async with db.execute(
                "SELECT question_id, value_json FROM assessment_answers WHERE tenant_id = ? AND assessment_id = ?",
                (self.tenant_id, assessment_id),
            ) as cur:
                return {r["question_id"]: json.loads(r["value_json"]) for r in await cur.fetchall()}

    async def save_answers(self, assessment_id: str, answers: dict, updated_by: str) -> None:
        async with _conn() as db:
            for qid, value in answers.items():
                await db.execute(
                    """INSERT INTO assessment_answers (tenant_id, assessment_id, question_id, value_json, updated_by)
                       VALUES (?,?,?,?,?)
                       ON CONFLICT(assessment_id, question_id) DO UPDATE SET
                         value_json = excluded.value_json, updated_by = excluded.updated_by,
                         updated_at = datetime('now')
                       WHERE assessment_answers.tenant_id = excluded.tenant_id""",
                    (self.tenant_id, assessment_id, qid, json.dumps(value, ensure_ascii=False), updated_by),
                )
            await db.commit()

    async def complete_assessment(self, assessment_id: str) -> None:
        async with _conn() as db:
            await db.execute(
                """UPDATE discovery_assessments SET status = 'completed', completed_at = datetime('now')
                   WHERE tenant_id = ? AND id = ?""",
                (self.tenant_id, assessment_id),
            )
            await db.commit()

    # Opportunities
    async def save_opportunities(self, assessment_id: str, opportunities: list[dict]) -> int:
        async with _conn() as db:
            async with db.execute(
                "SELECT COALESCE(MAX(generation), 0) FROM ai_opportunities WHERE tenant_id = ? AND assessment_id = ?",
                (self.tenant_id, assessment_id),
            ) as cur:
                generation = (await cur.fetchone())[0] + 1
            for opp in opportunities:
                await db.execute(
                    """INSERT INTO ai_opportunities
                       (id, tenant_id, assessment_id, generation, module, phase, priority_score, payload_json)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (opp["id"], self.tenant_id, assessment_id, generation, opp["module"], opp["phase"],
                     opp["priority_score"], json.dumps(opp, ensure_ascii=False)),
                )
            await db.commit()
        return generation

    async def latest_opportunities(self, assessment_id: str) -> tuple[int, list[dict]]:
        async with _conn() as db:
            async with db.execute(
                """SELECT generation, payload_json FROM ai_opportunities
                   WHERE tenant_id = ? AND assessment_id = ? AND generation = (
                       SELECT MAX(generation) FROM ai_opportunities WHERE tenant_id = ? AND assessment_id = ?)
                   ORDER BY priority_score DESC""",
                (self.tenant_id, assessment_id, self.tenant_id, assessment_id),
            ) as cur:
                rows = await cur.fetchall()
        if not rows:
            return 0, []
        return rows[0]["generation"], [json.loads(r["payload_json"]) for r in rows]

    # Plans
    async def save_plan(self, assessment_id: str, content: dict, markdown: str, created_by: str) -> dict:
        pid = _new_id()
        async with _conn() as db:
            async with db.execute(
                "SELECT COALESCE(MAX(version), 0) FROM transformation_plans WHERE tenant_id = ? AND assessment_id = ?",
                (self.tenant_id, assessment_id),
            ) as cur:
                version = (await cur.fetchone())[0] + 1
            await db.execute(
                """INSERT INTO transformation_plans
                   (id, tenant_id, assessment_id, version, content_json, markdown, created_by)
                   VALUES (?,?,?,?,?,?,?)""",
                (pid, self.tenant_id, assessment_id, version, json.dumps(content, ensure_ascii=False),
                 markdown, created_by),
            )
            await db.commit()
        return await self.get_plan(pid)

    async def get_plan(self, plan_id: str) -> dict | None:
        async with _conn() as db:
            async with db.execute(
                "SELECT * FROM transformation_plans WHERE tenant_id = ? AND id = ?", (self.tenant_id, plan_id)
            ) as cur:
                row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["content"] = json.loads(d.pop("content_json"))
        return d

    # Feedback
    async def create_feedback(
        self, *, fact_id: str, kind: str, proposed_value, note: str | None,
        submitted_by: str, submitted_by_type: str = "user",
    ) -> dict:
        fbid = _new_id()
        async with _conn() as db:
            await db.execute(
                """INSERT INTO brain_feedback
                   (id, tenant_id, fact_id, kind, proposed_value_json, note, submitted_by, submitted_by_type)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (fbid, self.tenant_id, fact_id, kind,
                 json.dumps(proposed_value, ensure_ascii=False) if proposed_value is not None else None,
                 note, submitted_by, submitted_by_type),
            )
            await db.commit()
        return await self.get_feedback(fbid)

    async def get_feedback(self, feedback_id: str) -> dict | None:
        async with _conn() as db:
            async with db.execute(
                "SELECT * FROM brain_feedback WHERE tenant_id = ? AND id = ?", (self.tenant_id, feedback_id)
            ) as cur:
                row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        pv = d.pop("proposed_value_json")
        d["proposed_value"] = json.loads(pv) if pv is not None else None
        return d

    async def list_feedback(self, status: str | None = None) -> list[dict]:
        sql = "SELECT id FROM brain_feedback WHERE tenant_id = ?"
        args: list = [self.tenant_id]
        if status:
            sql += " AND status = ?"
            args.append(status)
        async with _conn() as db:
            async with db.execute(sql + " ORDER BY created_at", args) as cur:
                ids = [r["id"] for r in await cur.fetchall()]
        return [await self.get_feedback(i) for i in ids]

    async def mark_feedback(self, feedback_id: str, status: str, resolved_by: str) -> None:
        async with _conn() as db:
            await db.execute(
                """UPDATE brain_feedback SET status = ?, resolved_by = ?, resolved_at = datetime('now')
                   WHERE tenant_id = ? AND id = ?""",
                (status, resolved_by, self.tenant_id, feedback_id),
            )
            await db.commit()

    # Agent assignments / scopes
    async def get_assignment(self, agent_role: str) -> dict | None:
        async with _conn() as db:
            async with db.execute(
                "SELECT * FROM agent_assignments WHERE tenant_id = ? AND agent_role = ?",
                (self.tenant_id, agent_role),
            ) as cur:
                row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        scope = d.pop("context_scope_json")
        d["context_scope"] = json.loads(scope) if scope else None
        return d

    async def list_assignments(self) -> list[dict]:
        async with _conn() as db:
            async with db.execute(
                "SELECT agent_role FROM agent_assignments WHERE tenant_id = ? ORDER BY agent_role", (self.tenant_id,)
            ) as cur:
                roles = [r["agent_role"] for r in await cur.fetchall()]
        return [await self.get_assignment(r) for r in roles]

    async def upsert_assignment(
        self, agent_role: str, updated_by: str, *, status: str | None = None,
        context_scope: dict | None = None, set_scope: bool = False,
    ) -> dict:
        existing = await self.get_assignment(agent_role)
        new_status = status or (existing["status"] if existing else "recommended")
        if set_scope:
            scope_json = json.dumps(context_scope) if context_scope is not None else None
        else:
            scope_json = json.dumps(existing["context_scope"]) if existing and existing["context_scope"] else None
        async with _conn() as db:
            await db.execute(
                """INSERT INTO agent_assignments (tenant_id, agent_role, status, context_scope_json, updated_by)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(tenant_id, agent_role) DO UPDATE SET
                     status = excluded.status, context_scope_json = excluded.context_scope_json,
                     updated_by = excluded.updated_by, updated_at = datetime('now')""",
                (self.tenant_id, agent_role, new_status, scope_json, updated_by),
            )
            await db.commit()
        return await self.get_assignment(agent_role)
