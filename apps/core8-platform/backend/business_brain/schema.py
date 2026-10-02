"""Business Brain tables. Every table carries tenant_id; see DESIGN.md §2."""

import database

SENSITIVITY_LEVELS = ["public", "internal", "confidential", "restricted"]

FACT_CATEGORIES = [
    "organization_profile", "products_services", "customer_personas", "roles",
    "systems", "processes", "policies", "tone_brand", "knowledge_sources",
    "kpis", "goals", "metrics", "pain_points", "approval_requirements",
]

FACT_SOURCE_TYPES = ["questionnaire", "manual", "correction", "agent", "import"]

MEMBER_ROLES = ["owner", "editor", "viewer"]

_DDL = """
CREATE TABLE IF NOT EXISTS tenants (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_by  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tenant_members (
    tenant_id   TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK(role IN ('owner','editor','viewer')),
    granted_by  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (tenant_id, user_id)
);

CREATE TABLE IF NOT EXISTS brain_facts (
    id            TEXT PRIMARY KEY,
    tenant_id     TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    fact_key      TEXT NOT NULL,
    version       INTEGER NOT NULL,
    category      TEXT NOT NULL,
    domain        TEXT NOT NULL DEFAULT 'general',
    value_json    TEXT NOT NULL,
    sensitivity   TEXT NOT NULL DEFAULT 'internal'
                  CHECK(sensitivity IN ('public','internal','confidential','restricted')),
    status        TEXT NOT NULL DEFAULT 'active'
                  CHECK(status IN ('active','superseded','retracted')),
    source_type   TEXT NOT NULL
                  CHECK(source_type IN ('questionnaire','manual','correction','agent','import')),
    source_ref    TEXT,
    confidence    REAL NOT NULL DEFAULT 1.0,
    created_by    TEXT NOT NULL,
    supersedes_id TEXT REFERENCES brain_facts(id),
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (tenant_id, fact_key, version)
);
CREATE INDEX IF NOT EXISTS ix_brain_facts_active
    ON brain_facts (tenant_id, status, category, domain);

CREATE TABLE IF NOT EXISTS discovery_assessments (
    id                    TEXT PRIMARY KEY,
    tenant_id             TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    questionnaire_version TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'in_progress'
                          CHECK(status IN ('in_progress','completed')),
    created_by            TEXT NOT NULL,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at          TEXT
);

CREATE TABLE IF NOT EXISTS assessment_answers (
    tenant_id     TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    assessment_id TEXT NOT NULL REFERENCES discovery_assessments(id) ON DELETE CASCADE,
    question_id   TEXT NOT NULL,
    value_json    TEXT NOT NULL,
    updated_by    TEXT NOT NULL,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (assessment_id, question_id)
);

CREATE TABLE IF NOT EXISTS ai_opportunities (
    id             TEXT PRIMARY KEY,
    tenant_id      TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    assessment_id  TEXT NOT NULL REFERENCES discovery_assessments(id) ON DELETE CASCADE,
    generation     INTEGER NOT NULL,
    module         TEXT NOT NULL,
    phase          TEXT NOT NULL CHECK(phase IN ('Now','Next','Later')),
    priority_score INTEGER NOT NULL,
    payload_json   TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_ai_opportunities_gen
    ON ai_opportunities (tenant_id, assessment_id, generation);

CREATE TABLE IF NOT EXISTS transformation_plans (
    id            TEXT PRIMARY KEY,
    tenant_id     TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    assessment_id TEXT NOT NULL REFERENCES discovery_assessments(id) ON DELETE CASCADE,
    version       INTEGER NOT NULL,
    status        TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved','archived')),
    content_json  TEXT NOT NULL,
    markdown      TEXT NOT NULL,
    created_by    TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (assessment_id, version)
);

CREATE TABLE IF NOT EXISTS brain_feedback (
    id                  TEXT PRIMARY KEY,
    tenant_id           TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    fact_id             TEXT NOT NULL REFERENCES brain_facts(id) ON DELETE CASCADE,
    kind                TEXT NOT NULL CHECK(kind IN ('correction','flag','comment')),
    proposed_value_json TEXT,
    note                TEXT,
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending','accepted','rejected')),
    submitted_by        TEXT NOT NULL,
    submitted_by_type   TEXT NOT NULL DEFAULT 'user' CHECK(submitted_by_type IN ('user','agent')),
    resolved_by         TEXT,
    resolved_at         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_assignments (
    tenant_id          TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_role         TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'recommended'
                       CHECK(status IN ('recommended','approved','deployed','disabled')),
    context_scope_json TEXT,
    updated_by         TEXT NOT NULL,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (tenant_id, agent_role)
);
"""


async def init_brain_schema() -> None:
    async with database.get_db() as db:
        await db.executescript(_DDL)
        await db.commit()
