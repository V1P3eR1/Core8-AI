"""Social Manager schema — versioned migrations on the shared SQLite file.

Every table is prefixed `sm_`. Migrations are applied in order and recorded in
`sm_migrations`, so a pre-existing database upgrades safely on boot.
"""

import aiosqlite

from database import get_db

MIGRATIONS: list[tuple[int, str]] = [
    (1, """
    CREATE TABLE IF NOT EXISTS sm_settings (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,              -- JSON
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sm_sources (
        id             TEXT PRIMARY KEY,
        title          TEXT NOT NULL,
        url            TEXT NOT NULL,
        url_hash       TEXT NOT NULL UNIQUE,    -- duplicate detection
        publisher      TEXT,
        published_at   TEXT,
        event_at       TEXT,
        discovered_at  TEXT NOT NULL DEFAULT (datetime('now')),
        summary        TEXT,
        relevance      TEXT,                     -- why it matters for Core8AI
        unknowns       TEXT,                     -- what is not known
        source_type    TEXT NOT NULL DEFAULT 'reporting'
                       CHECK(source_type IN ('official','reporting','opinion','inference','benchmark','demo')),
        confidence     TEXT NOT NULL DEFAULT 'medium' CHECK(confidence IN ('low','medium','high')),
        trend_verified INTEGER NOT NULL DEFAULT 0,  -- 1 only with accessible evidence
        angle          TEXT,                        -- original content angle
        topic          TEXT,
        status         TEXT NOT NULL DEFAULT 'new'
                       CHECK(status IN ('new','reviewed','used','dismissed')),
        is_demo        INTEGER NOT NULL DEFAULT 0,
        provider       TEXT,
        raw            TEXT,                        -- JSON, provider payload (untrusted data)
        created_at     TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sm_ideas (
        id             TEXT PRIMARY KEY,
        title          TEXT NOT NULL,
        pillar         TEXT NOT NULL,
        audience       TEXT NOT NULL,
        problem        TEXT NOT NULL,
        core_message   TEXT NOT NULL,
        desired_action TEXT NOT NULL,
        format         TEXT NOT NULL CHECK(format IN ('reel','carousel','image','story')),
        business_goal  TEXT NOT NULL,
        measurement    TEXT NOT NULL,
        source_ids     TEXT NOT NULL DEFAULT '[]',   -- JSON array of sm_sources.id
        notes          TEXT,
        status         TEXT NOT NULL DEFAULT 'new'
                       CHECK(status IN ('new','shortlisted','drafted','rejected')),
        is_demo        INTEGER NOT NULL DEFAULT 0,
        created_at     TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sm_assets (
        id              TEXT PRIMARY KEY,
        filename        TEXT NOT NULL,
        original_name   TEXT,
        media_type      TEXT NOT NULL CHECK(media_type IN ('image','video')),
        mime            TEXT NOT NULL,
        bytes           INTEGER NOT NULL,
        width           INTEGER,
        height          INTEGER,
        duration_s      REAL,
        sha256          TEXT NOT NULL,
        ownership       TEXT NOT NULL DEFAULT 'owner_upload',  -- owner_upload | rendered | generated | third_party
        permission_note TEXT,
        alt_text        TEXT,
        caption         TEXT,
        brief           TEXT,
        spec_check      TEXT,                     -- JSON result of validate_for_instagram
        is_demo         INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sm_content_items (
        id              TEXT PRIMARY KEY,
        idea_id         TEXT REFERENCES sm_ideas(id),
        format          TEXT NOT NULL CHECK(format IN ('reel','carousel','image','story')),
        title           TEXT NOT NULL,
        pillar          TEXT,
        audience        TEXT,
        status          TEXT NOT NULL DEFAULT 'draft'
                        CHECK(status IN ('draft','needs_review','approved','scheduled','publishing',
                                         'published','failed','needs_manual_review','rejected','paused')),
        package         TEXT NOT NULL DEFAULT '{}',  -- JSON production package
        caption         TEXT NOT NULL DEFAULT '',
        asset_ids       TEXT NOT NULL DEFAULT '[]',  -- JSON array, ordered
        cover_asset_id  TEXT,
        scheduled_for   TEXT,                        -- UTC ISO 'YYYY-MM-DD HH:MM:SS'
        account_id      TEXT,                        -- ig_user_id bound at approval/scheduling
        sensitive_flags TEXT NOT NULL DEFAULT '[]',  -- JSON array of flag codes
        fact_check      TEXT,                        -- JSON fact-checker result
        production_status TEXT NOT NULL DEFAULT 'script_only',
        review_notes    TEXT,
        version         INTEGER NOT NULL DEFAULT 1,
        is_demo         INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sm_approvals (
        id              TEXT PRIMARY KEY,
        content_item_id TEXT NOT NULL REFERENCES sm_content_items(id),
        account_id      TEXT NOT NULL,
        format          TEXT NOT NULL,
        caption_hash    TEXT NOT NULL,
        assets_hash     TEXT NOT NULL,            -- hash over ordered asset sha256s
        scheduled_for   TEXT,
        settings_hash   TEXT NOT NULL,            -- other publication-relevant settings
        binding_hash    TEXT NOT NULL,            -- hash over all of the above
        approved_by     TEXT NOT NULL,
        approved_at     TEXT NOT NULL DEFAULT (datetime('now')),
        status          TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active','invalidated','consumed')),
        invalidated_reason TEXT,
        invalidated_at  TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_sm_approvals_item ON sm_approvals(content_item_id, status);

    CREATE TABLE IF NOT EXISTS sm_publications (
        id               TEXT PRIMARY KEY,
        content_item_id  TEXT NOT NULL REFERENCES sm_content_items(id),
        approval_id      TEXT REFERENCES sm_approvals(id),
        publication_key  TEXT NOT NULL UNIQUE,   -- item id + binding hash: one publication per approved version
        account_id       TEXT NOT NULL,
        mode             TEXT NOT NULL CHECK(mode IN ('live','mock')),
        state            TEXT NOT NULL DEFAULT 'queued'
                         CHECK(state IN ('queued','claimed','container_created','container_ready',
                                         'publish_requested','published','failed',
                                         'needs_manual_review','cancelled')),
        scheduled_for    TEXT NOT NULL,
        container_id     TEXT,
        child_container_ids TEXT,                -- JSON
        provider_media_id TEXT,
        permalink        TEXT,
        attempts         INTEGER NOT NULL DEFAULT 0,
        last_error       TEXT,
        error_class      TEXT,                   -- retryable | permanent | unknown
        claimed_by       TEXT,
        claimed_at       TEXT,
        lock_expires_at  TEXT,
        publish_requested_at TEXT,
        published_at     TEXT,
        log              TEXT NOT NULL DEFAULT '[]',  -- JSON array of {at, event, detail}
        created_at       TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_sm_publications_state ON sm_publications(state, scheduled_for);

    CREATE TABLE IF NOT EXISTS sm_jobs (
        id            TEXT PRIMARY KEY,
        type          TEXT NOT NULL,             -- research | planning | weekly_report | publish | drafts | metrics | token_check
        schedule_key  TEXT,                      -- set for scheduled jobs; unique per (key, run_at)
        run_at        TEXT NOT NULL,             -- UTC
        status        TEXT NOT NULL DEFAULT 'pending'
                      CHECK(status IN ('pending','running','succeeded','failed','skipped','cancelled')),
        claimed_by    TEXT,
        claimed_at    TEXT,
        lock_expires_at TEXT,
        attempts      INTEGER NOT NULL DEFAULT 0,
        max_attempts  INTEGER NOT NULL DEFAULT 3,
        payload       TEXT NOT NULL DEFAULT '{}',
        result        TEXT,
        error         TEXT,
        started_at    TEXT,
        finished_at   TEXT,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_sm_jobs_schedule ON sm_jobs(schedule_key, run_at)
        WHERE schedule_key IS NOT NULL;
    CREATE INDEX IF NOT EXISTS idx_sm_jobs_status ON sm_jobs(status, run_at);

    CREATE TABLE IF NOT EXISTS sm_schedules (
        key         TEXT PRIMARY KEY,            -- daily_research | weekly_planning | weekly_report
        job_type    TEXT NOT NULL,
        hour        INTEGER NOT NULL,
        minute      INTEGER NOT NULL,
        weekday     INTEGER,                     -- 0=Mon..6=Sun; NULL = daily
        enabled     INTEGER NOT NULL DEFAULT 1,
        last_run_at TEXT,
        next_run_at TEXT,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sm_metrics (
        id              TEXT PRIMARY KEY,
        scope           TEXT NOT NULL CHECK(scope IN ('account','post')),
        content_item_id TEXT,
        provider_media_id TEXT,
        metric          TEXT NOT NULL,
        value           REAL NOT NULL,
        period_start    TEXT,
        period_end      TEXT,
        source          TEXT NOT NULL CHECK(source IN ('api','manual','demo')),
        note            TEXT,
        fetched_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sm_leads (
        id            TEXT PRIMARY KEY,
        name          TEXT NOT NULL,
        handle        TEXT,
        lead_date     TEXT,
        source        TEXT,
        business_type TEXT,
        need          TEXT,
        status        TEXT NOT NULL DEFAULT 'new'
                      CHECK(status IN ('new','contacted','qualified','proposal','won','lost','archived')),
        next_action   TEXT,
        notes         TEXT,
        consent_note  TEXT,
        is_demo       INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sm_reports (
        id          TEXT PRIMARY KEY,
        kind        TEXT NOT NULL DEFAULT 'weekly',
        period_start TEXT NOT NULL,
        period_end   TEXT NOT NULL,
        content     TEXT NOT NULL,               -- JSON
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sm_audit_log (
        id         TEXT PRIMARY KEY,
        actor      TEXT NOT NULL,                -- user email / 'worker' / 'system'
        action     TEXT NOT NULL,
        entity     TEXT,
        entity_id  TEXT,
        details    TEXT,                         -- JSON (redacted)
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sm_ai_usage (
        id            TEXT PRIMARY KEY,
        job_id        TEXT,
        task          TEXT NOT NULL,
        provider      TEXT NOT NULL,
        model         TEXT,
        input_tokens  INTEGER NOT NULL DEFAULT 0,
        output_tokens INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sm_inbound_messages (
        id            TEXT PRIMARY KEY,
        kind          TEXT NOT NULL CHECK(kind IN ('comment','dm')),
        provider_id   TEXT,
        author        TEXT,
        text          TEXT NOT NULL,             -- untrusted data
        received_at   TEXT NOT NULL DEFAULT (datetime('now')),
        draft_reply   TEXT,
        reply_status  TEXT NOT NULL DEFAULT 'draft_only'
                      CHECK(reply_status IN ('draft_only','approved_not_sent','sent','dismissed')),
        flagged       INTEGER NOT NULL DEFAULT 0,
        flag_reasons  TEXT,
        is_demo       INTEGER NOT NULL DEFAULT 0
    );
    """),
    (2, """
    CREATE TABLE IF NOT EXISTS sm_media_grants (
        asset_id   TEXT PRIMARY KEY,
        revoked_at TEXT
    );
    """),
]


async def init_social_schema() -> None:
    async with get_db() as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS sm_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now')))""")
        await db.commit()
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT version FROM sm_migrations") as cur:
            applied = {r["version"] for r in await cur.fetchall()}
        for version, sql in MIGRATIONS:
            if version in applied:
                continue
            await db.executescript(sql)
            await db.execute("INSERT INTO sm_migrations (version) VALUES (?)", (version,))
            await db.commit()
