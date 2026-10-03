import aiosqlite
import json
import os

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "core8.db"))

# Operational tables that carry tenant_id (CORE8-005).
_TENANT_SCOPED_TABLES = [
    "conversations", "messages", "leads", "events", "design_docs", "content_plans",
    "plan_artifacts", "ig_accounts", "scheduled_posts", "media_assets",
]


def get_db() -> aiosqlite.Connection:
    db = aiosqlite.connect(DB_PATH)
    return db


_SEED_AGENTS = [
    (
        "general",
        "General Assistant",
        "A general-purpose AI agent for Core8-AI",
        "claude-sonnet-4-6",
        "You are a helpful AI assistant for Core8-AI. You help business owners automate their work, manage tasks, and grow their businesses. You are precise, professional, and direct.",
    ),
    (
        "leads",
        "Lead Manager",
        "Tracks and manages sales leads and CRM data",
        "claude-sonnet-4-6",
        """You are Core8-AI's Lead Manager — a precision CRM agent.
Your job: capture, track, qualify, and advance sales leads.

On every interaction:
- Be direct and data-driven. No fluff.
- Always confirm what you've done (e.g. "Lead created: Acme Corp / John Smith").
- Use tools to read/write lead data — never invent information.
- When asked to create a lead, extract: name, email, company, status, source from the user's message.
- Valid statuses: new, contacted, qualified, proposal, won, lost.
- When listing leads, format as a clean table.
- Proactively suggest follow-ups based on lead age and status.
""",
    ),
    (
        "calendar",
        "Calendar Agent",
        "Manages meetings, events, and scheduling",
        "claude-sonnet-4-6",
        """You are Core8-AI's Calendar Agent — a precision scheduling agent.
Your job: create, list, and manage calendar events.

On every interaction:
- Be concise and precise with times. Always confirm timezone if ambiguous (default: Israel Standard Time, UTC+3).
- Always confirm what you've done (e.g. "Event created: Team Standup / Mon 09:00–09:30").
- Use tools to read/write events — never invent event data.
- When finding free slots, check for overlaps before suggesting times.
- Format event lists as clean tables with date, time, title, duration.
- start_time and end_time must be ISO 8601 strings (e.g. 2026-05-17T09:00:00).
""",
    ),
    (
        "design",
        "Head of Design",
        "Creates UI mockups, design briefs, and component specs (7-tier system)",
        "claude-sonnet-4-6",
        """You are Core8-AI's Head of Design — a senior product designer who thinks in systems.
You operate a strict 7-tier design workflow. Never skip tiers.

═══ TIER 0 — INTERVIEW ═══
Before writing a single line of code or markdown, interview the user:
- What product / feature / screen?
- Who is the end user? What is their job to be done?
- Brand personality (3 adjectives)?
- Existing brand colors / fonts? (ask for reference images if available)
- Viewport priority: mobile / desktop / both?
- Key components needed?
Do not proceed to Tier 1 until all answers are collected.

═══ TIER 1 — DOCUMENT MODEL ═══
Create three files per project:
1. design.md — master design spec (brand, colors, typography, grid, motion)
2. brief.md — one-page creative brief (vision, audience, tone, constraints)
3. features/<slug>.md — per-screen/feature spec (layout, components, states, copy)
Use the write_design_doc tool to create and update these files.

═══ TIER 2 — COMPONENT FRAMEWORK ═══
All UI is built with Next.js 15 + Tailwind 3.4 + shadcn/ui.
Never generate raw HTML. Always specify real shadcn component names.
Specify exact Tailwind classes — no approximations.

═══ TIER 3 — COMPOSITION ═══
When a feature spec is complete, use run_preview_build to scaffold the component.
Pass the full feature spec as context. The build creates a static preview.

═══ TIER 4 — COMPONENT CATALOG ═══
Source components from this priority order:
1. shadcn/ui (primary)
2. MagicUI (animations, particles, shimmer)
3. Aceternity UI (cards, spotlight, background effects)
4. Reactbits (micro-interactions)
5. Framer Motion (page transitions, layout animations)
Always specify the exact import path.

═══ TIER 5 — VISUAL ELEMENTS ═══
For hero images, illustrations, icons: describe them precisely using the
write_design_doc tool (images/ subfolder). Use descriptive filenames.
Specify: subject, style, color palette, mood, aspect ratio.

═══ TIER 6 — BRIEF IS LAW ═══
Every decision must trace back to brief.md.
If a request conflicts with the brief, flag it explicitly:
"⚠ BRIEF CONFLICT: [what conflicts] — [recommendation]"
Never silently violate the brief.

═══ TIER 7 — REFERENCE ANCHORING ═══
When the user provides reference images, use read_design_doc to load them
into context. Extract: color codes, type scales, spacing rhythm, component patterns.
Document extracted values in design.md before proceeding.

═══ COST AWARENESS ═══
First dispatch per project: ~$3–6. Subsequent screens: ~$1–3. Work efficiently.
Always ask: "Which screen/feature should I tackle first?"
""",
    ),
    (
        "instagram",
        "Instagram Growth Agent",
        "Runs the 7-step Instagram theme-page growth workflow",
        "claude-sonnet-4-6",
        """You are Core8-AI's Instagram Growth Agent. You take a business from "I want an
Instagram theme page" to a complete, ready-to-run growth plan, using a fixed
7-step workflow. Each step is a tool, and behind each tool is a specialist.

THE 7 STEPS
1. run_niche_finder       — 10 viable theme-page niches
2. run_viral_blueprint    — 20 viral content ideas for the chosen niche
3. run_caption_generator  — a viral caption for one specific content idea
4. run_hashtag_formula    — 15 hashtags + 5 hooks for the niche
5. run_content_schedule   — a 30-day content calendar
6. run_monetization_map   — 5 ways to monetize the page
7. run_automation_setup   — set the page to publish on autopilot

HOW YOU OPERATE
- First understand the user's interests and goals. Then call create_content_plan
  to open a plan — every step tool needs that plan_id. Use one plan per page.
- Run ONE step at a time. After each step, show the user the result and ask
  before continuing. The user drives — never run the whole workflow unprompted.
- After run_niche_finder, present the 10 niches and ask the user to choose one.
  Record the choice with update_content_plan(plan_id, niche="<their choice>").
  Steps 2, 4, 5, and 6 will not run until a niche is recorded.
- For run_caption_generator, ask which content idea (from the viral blueprint)
  the user wants captioned, and pass it as content_idea.
- If a step tool returns a dependency error, run the prerequisite step it names,
  then retry the step.
- Step 7 is not fully available yet — live Instagram publishing is still being
  built. If the user reaches it, explain that steps 1-6 already give them a
  complete plan they can post manually, and that auto-publishing is coming.

RULES
- Never invent niches, content ideas, captions, hashtags, schedules, or numbers.
  Those come only from the step tools. You conduct; the tools produce.
- Use get_content_plan to check progress and read_plan_artifact to re-show a
  previous step's output.
- Be precise, professional, and direct. Confirm what you did after each step.
  You are an operator, not a hype machine.
""",
    ),
]


# Tool scoping for seeded agents — agent_id -> allowed tool names.
# Agents not listed here see every registered tool (allowed_tools = NULL).
_AGENT_TOOL_SCOPES: dict[str, list[str]] = {
    "instagram": [
        "connect_instagram", "list_ig_accounts",
        "create_content_plan", "list_content_plans", "get_content_plan",
        "update_content_plan", "read_plan_artifact",
        "run_niche_finder", "run_viral_blueprint", "run_caption_generator",
        "run_hashtag_formula", "run_content_schedule", "run_monetization_map",
        "run_automation_setup",
        "queue_post", "list_scheduled_posts", "cancel_scheduled_post",
        "generate_post_image", "list_media_assets",
        "get_account_insights", "get_post_insights",
    ],
}


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS agents (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT,
                model       TEXT NOT NULL DEFAULT 'claude-sonnet-4-6',
                system_prompt TEXT,
                allowed_tools TEXT,   -- JSON array of tool names; NULL = all tools
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS conversations (
                tenant_id   TEXT NOT NULL,
                id          TEXT PRIMARY KEY,
                agent_id    TEXT NOT NULL REFERENCES agents(id),
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS messages (
                tenant_id   TEXT NOT NULL,
                id              TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                role            TEXT NOT NULL CHECK(role IN ('user','assistant','tool')),
                content         TEXT NOT NULL,
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS leads (
                tenant_id   TEXT NOT NULL,
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                email       TEXT,
                company     TEXT,
                status      TEXT NOT NULL DEFAULT 'new',
                source      TEXT,
                notes       TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS events (
                tenant_id   TEXT NOT NULL,
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                start_time  TEXT NOT NULL,
                end_time    TEXT NOT NULL,
                description TEXT,
                attendees   TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS design_docs (
                tenant_id   TEXT NOT NULL,
                id          TEXT PRIMARY KEY,
                project     TEXT NOT NULL,
                path        TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(tenant_id, project, path)
            );

            CREATE TABLE IF NOT EXISTS users (
                id            TEXT PRIMARY KEY,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'operator',
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                last_login    TEXT
            );

            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id         TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS content_plans (
                tenant_id   TEXT NOT NULL,
                id            TEXT PRIMARY KEY,
                owner_user_id TEXT REFERENCES users(id),  -- nullable until multi-tenancy is decided
                niche         TEXT,
                status        TEXT NOT NULL DEFAULT 'planning'
                              CHECK(status IN ('planning','scheduled','active')),
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS plan_artifacts (
                tenant_id   TEXT NOT NULL,
                id          TEXT PRIMARY KEY,
                plan_id     TEXT NOT NULL REFERENCES content_plans(id),
                step        TEXT NOT NULL
                            CHECK(step IN ('niche','viral','caption','hashtag','schedule','monetize')),
                content     TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(plan_id, step)
            );

            -- One connected Instagram Business account per tenant (id = tenant_id).
            -- access_token is Fernet-encrypted at rest.
            CREATE TABLE IF NOT EXISTS ig_accounts (
                id               TEXT PRIMARY KEY,
                tenant_id        TEXT NOT NULL,
                ig_user_id       TEXT NOT NULL,
                fb_page_id       TEXT NOT NULL,
                username         TEXT,
                access_token     TEXT NOT NULL,
                token_expires_at TEXT,
                connected_at     TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Posts queued for the publishing scheduler.
            -- For carousel posts media_urls (JSON array of 2-10 urls) holds the
            -- children; media_url stays NOT NULL and is set to the first url.
            CREATE TABLE IF NOT EXISTS scheduled_posts (
                tenant_id   TEXT NOT NULL,
                id            TEXT PRIMARY KEY,
                plan_id       TEXT REFERENCES content_plans(id),
                post_type     TEXT NOT NULL CHECK(post_type IN ('image','reel','carousel')),
                media_url     TEXT NOT NULL,
                media_urls    TEXT,                   -- JSON array, carousel only
                caption       TEXT,
                scheduled_for TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'pending'
                              CHECK(status IN ('pending','publishing','published','failed','cancelled')),
                ig_media_id   TEXT,
                attempts      INTEGER NOT NULL DEFAULT 0,
                last_error    TEXT,
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- The media library: uploaded and Gemini-generated post media.
            CREATE TABLE IF NOT EXISTS media_assets (
                tenant_id   TEXT NOT NULL,
                id          TEXT PRIMARY KEY,
                filename    TEXT NOT NULL,
                source      TEXT NOT NULL CHECK(source IN ('upload','generated')),
                media_type  TEXT NOT NULL CHECK(media_type IN ('image','video')),
                prompt      TEXT,
                plan_id     TEXT REFERENCES content_plans(id),
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        await db.commit()

    # Schema migrations for pre-existing databases
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("PRAGMA table_info(agents)") as cur:
            agent_cols = [r[1] for r in await cur.fetchall()]
        if "allowed_tools" not in agent_cols:
            await db.execute("ALTER TABLE agents ADD COLUMN allowed_tools TEXT")
            await db.commit()

        # scheduled_posts v2: add 'carousel' to post_type CHECK + media_urls column.
        # SQLite cannot ALTER a CHECK constraint, so we rebuild the table preserving data.
        async with db.execute("PRAGMA table_info(scheduled_posts)") as cur:
            sp_cols = [r[1] for r in await cur.fetchall()]
        if sp_cols and "media_urls" not in sp_cols:
            await db.executescript("""
                ALTER TABLE scheduled_posts RENAME TO _scheduled_posts_v1;
                CREATE TABLE scheduled_posts (
                    id            TEXT PRIMARY KEY,
                    plan_id       TEXT REFERENCES content_plans(id),
                    post_type     TEXT NOT NULL CHECK(post_type IN ('image','reel','carousel')),
                    media_url     TEXT NOT NULL,
                    media_urls    TEXT,
                    caption       TEXT,
                    scheduled_for TEXT NOT NULL,
                    status        TEXT NOT NULL DEFAULT 'pending'
                                  CHECK(status IN ('pending','publishing','published','failed','cancelled')),
                    ig_media_id   TEXT,
                    attempts      INTEGER NOT NULL DEFAULT 0,
                    last_error    TEXT,
                    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
                );
                INSERT INTO scheduled_posts
                    (id, plan_id, post_type, media_url, caption, scheduled_for, status,
                     ig_media_id, attempts, last_error, created_at, updated_at)
                SELECT id, plan_id, post_type, media_url, caption, scheduled_for, status,
                       ig_media_id, attempts, last_error, created_at, updated_at
                FROM _scheduled_posts_v1;
                DROP TABLE _scheduled_posts_v1;
            """)
            await db.commit()

    # CORE8-005: tenant-scope legacy tables (one shared DB, every row labelled by client).
    # Existing rows are assigned to the internal tenant.
    async with aiosqlite.connect(DB_PATH) as db:
        for table in _TENANT_SCOPED_TABLES:
            async with db.execute(f"PRAGMA table_info({table})") as cur:
                cols = [r[1] for r in await cur.fetchall()]
            if cols and "tenant_id" not in cols:
                await db.execute(
                    f"ALTER TABLE {table} ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'core8-internal'"
                )
            await db.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant ON {table} (tenant_id)")
        # design_docs: (project, path) must be unique per tenant, not globally.
        async with db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='design_docs'"
        ) as cur:
            ddl = (await cur.fetchone())[0]
        if "UNIQUE(tenant_id, project, path)" not in ddl:
            await db.executescript("""
                ALTER TABLE design_docs RENAME TO _design_docs_v1;
                CREATE TABLE design_docs (
                    tenant_id   TEXT NOT NULL,
                    id          TEXT PRIMARY KEY,
                    project     TEXT NOT NULL,
                    path        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(tenant_id, project, path)
                );
                INSERT INTO design_docs (tenant_id, id, project, path, content, created_at, updated_at)
                SELECT tenant_id, id, project, path, content, created_at, updated_at FROM _design_docs_v1;
                DROP TABLE _design_docs_v1;
                CREATE INDEX IF NOT EXISTS ix_design_docs_tenant ON design_docs (tenant_id);
            """)
        # ig_accounts: the old singleton row 'primary' becomes the internal tenant's account.
        await db.execute(
            "UPDATE ig_accounts SET id = tenant_id WHERE id = 'primary'"
        )
        await db.commit()

    # Seed specialist agents. allowed_tools is reconciled on every boot — it is a
    # security boundary and must always match _AGENT_TOOL_SCOPES, even for an
    # agent row created by an earlier build. Other fields keep insert-if-absent
    # semantics (ON CONFLICT updates allowed_tools only).
    async with aiosqlite.connect(DB_PATH) as db:
        for agent_id, name, desc, model, prompt in _SEED_AGENTS:
            scope = _AGENT_TOOL_SCOPES.get(agent_id)
            await db.execute(
                """INSERT INTO agents
                       (id, name, description, model, system_prompt, allowed_tools)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET allowed_tools=excluded.allowed_tools""",
                (agent_id, name, desc, model, prompt,
                 json.dumps(scope) if scope else None),
            )
        await db.commit()
