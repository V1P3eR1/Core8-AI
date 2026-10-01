# Instagram Growth Agent — Architecture & Workflow Spec

**Status:** Phases 0–7 built (backend + calendar UI complete + hardened; live publishing + image generation pending external accounts)
**Owner:** Lev Shoihat
**Last updated:** 2026-05-19
**Codename:** `instagram` agent

---

## 1. Purpose

A Core8-AI specialist agent that takes a user from *"I want to start an Instagram
theme page"* to *"posts publish themselves on a schedule"*. It runs a fixed
7-step growth workflow, then operates the page on autopilot via the Instagram
Graph API.

This is a **full-automation** build: the agent connects to a real Instagram
Business account and publishes content. It is not a content-suggestion chatbot.

### Goal
One conversational agent the user talks to. Behind it, a parent **orchestrator**
dispatches to **6 planning sub-agents** — one per planning step — and a
**scheduler** that publishes queued posts at their target times.

---

## 2. Scope

**In scope**
- 7-step content workflow (section 3); steps 1-6 each backed by a sub-agent.
- Instagram Graph API integration: account connect (OAuth), publish, insights.
- A scheduler that publishes queued posts at future times.
- New DB tables for connected accounts, content plans, and the publish queue.

**Out of scope (this build)**
- Multi-platform (TikTok, YouTube Shorts) — design leaves room, does not build it.
- AI *video* generation. Post images can now be generated (Gemini/Imagen,
  Phase 5); video/reel media is user-supplied via upload.
- Comment/DM automation. Out of scope to keep the Meta App Review surface small.

---

## 3. The 7-step workflow

Source: the "AI media scope" prompt set. Steps 1–6 each have a sub-agent;
step 7 (Automation Setup) is pure logic — a readiness check, no LLM.

| # | Step | Sub-agent | Input | Output artifact |
|---|------|-----------|-------|-----------------|
| 1 | Niche Finder | `ig-niche` | user interests/goals | 10 niches: competition, growth, monetization scored |
| 2 | Viral Content Blueprint | `ig-viral` | chosen niche | 20 reel/carousel ideas (no-face friendly) |
| 3 | Caption Generator | `ig-caption` | a content idea | viral caption: hook + body + CTA |
| 4 | Hashtag & Hook Formula | `ig-hashtag` | niche | 15 hashtags + 5 scroll-stopping hooks |
| 5 | Content Schedule | `ig-schedule` | niche + ideas | 30-day calendar (date, type, idea, slot) |
| 6 | Monetization Map | `ig-monetize` | niche | 5 monetization paths (affiliate/shoutout/product) |
| 7 | Automation Setup | *(no sub-agent)* | schedule + account | readiness check — `queue_post` schedules posts to `scheduled_posts` |

Steps 1–6 are **planning** (produce artifacts, no external side effects).
Step 7 is **execution** (touches the live account — gated, see section 9).

The user does not have to run all 7, or run them in order. Step dependencies
(e.g. viral ideas need a chosen niche) are enforced in the **tool handlers**,
not the prompts — see section 4.4.

---

## 4. Architecture

### 4.1 Agent topology — "sub-agents as tools"

The cleanest fit for the existing codebase (`BaseAgent` + global `ToolRegistry`)
is the **agents-as-tools** pattern:

```
User  ──ws──►  instagram (parent orchestrator, a seed agent in DB)
                 │  system prompt = workflow conductor
                 │  tools = 7 step tools + account/insights tools
                 │
                 ├─ tool: run_niche_finder      ─► spawns ig-niche  sub-agent
                 ├─ tool: run_viral_blueprint   ─► spawns ig-viral  sub-agent
                 ├─ tool: run_caption_generator ─► spawns ig-caption sub-agent
                 ├─ tool: run_hashtag_formula   ─► spawns ig-hashtag sub-agent
                 ├─ tool: run_content_schedule  ─► spawns ig-schedule sub-agent
                 ├─ tool: run_monetization_map  ─► spawns ig-monetize sub-agent
                 ├─ tool: run_automation_setup  ─► pure logic (readiness check)
                 │
                 ├─ tool: connect_instagram / list_ig_accounts / queue_post / …
                 └─ scheduler ─► publishes queued posts at their scheduled time
```

Each step tool's handler builds a message list and calls
`BaseAgent(sub_config).run(...)`, collecting the sub-agent's final text and any
artifact it persisted. The parent never sees the sub-agent's internal tool
calls — only the returned artifact. This keeps the parent's context small and
each sub-agent's prompt sharp and single-purpose.

The 6 planning sub-agent `AgentConfig`s live **in code**
(`agents/instagram_subagents.py`), not as DB seed rows — they are internal
machinery, not user-facing agents in the sidebar. Only the parent `instagram`
agent is a seed row. There is no 7th sub-agent — step 7 (`run_automation_setup`)
is a pure-logic readiness check; publishing is the scheduler's job.

### 4.2 Sub-agent dispatch

`BaseAgent.run()` returns `(final_text, stop_reason)` (Phase 0). The step-tool
**handler** is the deterministic orchestrator and does every side effect, so the
sub-agent is a pure-generation call:

```python
async def run_viral_blueprint(plan_id: str) -> dict:
    plan, err = await _require_plan(plan_id)         # 1. plan exists?
    if err: return err
    niche = (plan.get("niche") or "").strip()
    if not niche:                                    # 2. dependency guard
        return {"error": "no_niche", "message": _NO_NICHE}
    text, sub_err = await _run_subagent(             # 3. spawn (try/except wrapped)
        VIRAL_BLUEPRINT, f"Chosen niche: {niche}\n\n...")
    if sub_err: return {"error": sub_err}
    return await _finish(plan_id, "viral", text)     # 4. save artifact + return
```

The handler reads upstream artifacts and injects them into the prompt; the
sub-agent only generates. `_run_subagent` wraps the call in try/except, so a
sub-agent failure becomes a clean tool error instead of crashing the parent's
tool loop.

### 4.3 Per-agent tool scoping

`BaseAgent.run()` scopes its toolset through `AgentConfig.allowed_tools`
(`None` = every tool, a list = only those, `[]` = none). For DB-seeded agents
the scope is persisted in the `agents.allowed_tools` column (JSON), parsed by
`load_agent()`. This keeps planning sub-agents from ever reaching publishing
tools, and keeps the parent from recursing into its own step tools.

| Agent | Model | Tools |
|-------|-------|-------|
| `ig-niche` … `ig-monetize` (6) | Sonnet / Haiku | none — `allowed_tools=[]` |
| `instagram` (parent) | Sonnet | 17 — account, plan, step, and queue tools |

The 6 planning sub-agents need **no tools** — the step-tool handler does all
artifact I/O (§4.2), so each is a pure-generation call. The parent is scoped to
exactly its 17 workflow tools, not the leads/calendar/design tools.

**Model tiering.** `AgentConfig` carries `model`, so per-sub-agent model choice
is free. The mechanical steps — `ig-caption`, `ig-hashtag` — produce short,
templated output and run on **Haiku** (`claude-haiku-4-5-20251001`): cheaper and
faster, no quality loss. The steps that need real reasoning or calendar logic —
niche, viral, schedule, monetize — run on **Sonnet** (`claude-sonnet-4-6`).

### 4.4 Step dependency enforcement — in handlers, not prompts

The parent orchestrator is an LLM, and LLMs are unreliable state machines. Do
**not** rely on the parent's prompt to sequence steps correctly. Each step tool
handler verifies its prerequisites before spawning its sub-agent (the guard in
§4.2) and returns a structured error if they are missing:

| Step tool | Requires |
|-----------|----------|
| `run_niche_finder` | content plan exists |
| `run_viral_blueprint` | chosen niche (`content_plans.niche`) |
| `run_caption_generator` | a `content_idea` argument |
| `run_hashtag_formula` | chosen niche |
| `run_content_schedule` | chosen niche + `viral` artifact |
| `run_monetization_map` | chosen niche |
| `run_automation_setup` | `schedule` artifact + a connected account |

A wrong-order call fails cleanly and tells the parent how to recover, instead of
producing a plausible-but-wrong artifact off missing input. This is the
engineering version of "measure twice": the guard lives in the data layer where
it cannot be talked around, not in a probabilistic instruction.

---

## 5. Instagram Graph API integration

This is the highest-risk and highest-effort part. Meta's rules are strict —
flagging the real constraints up front so they shape the build, not surprise it.

### 5.1 Hard prerequisites
- The target IG account must be a **Business or Creator** account.
- It must be **linked to a Facebook Page**.
- A **Meta app** (developer.facebook.com) with the *Instagram Graph API* product.
- **App Review** for these permissions before going live:
  `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`,
  `pages_show_list`, `pages_read_engagement`, `business_management`.

> **Calendar dependency:** App Review takes days-to-weeks and is not in our
> control. During development the app stays in *Development mode* and works
> only for accounts added as **app testers**. Plan the build so steps 1–6 and
> the scheduler are fully testable without a reviewed app.

### 5.2 OAuth & token lifecycle
- The `connect_instagram` tool builds the Meta OAuth consent URL (with a CSRF
  `state`); the user opens it. Only the **callback** is an HTTP route —
  `/api/instagram/oauth/callback` — there is no `/oauth/start` endpoint.
- Callback flow: validate `state` → exchange code → short-lived token →
  **long-lived user token (~60 days)** → resolve the Page's linked IG account →
  store `ig_user_id`, `fb_page_id`, `username`, encrypted token.
- Tokens are **secrets**: Fernet-encrypted at rest (`IG_TOKEN_ENC_KEY`), never
  returned over the API or in tool results.
- Long-lived token refresh runs as a background job (`token_refresher.py`):
  hourly check, refreshes when fewer than 7 days remain. Started in `lifespan`.

### 5.3 Publishing flow (two-step, container-based)
1. `POST /{ig-user-id}/media` — create a media *container* with the public
   media URL + caption. Returns a `creation_id`.
2. For video/Reels: poll `GET /{container-id}?fields=status_code` until
   `FINISHED` (can take tens of seconds).
3. `POST /{ig-user-id}/media_publish` with `creation_id` — publishes.

**Media hosting requirement:** Instagram *fetches* the media from a public URL —
it does not accept file uploads. The agent needs a place to host post media
(e.g. an S3/R2 bucket or a static `nginx`-served path). This is a real
infra dependency for step 7, not an afterthought.

### 5.4 "Scheduling" — we build it, the API does not
The Graph API **publishes immediately**; it has no future-publish parameter.
Meta's own scheduling lives only in the Business Suite UI. So:

- `queue_post` writes rows to `scheduled_posts` with a `scheduled_for` time (UTC).
- A **Core8 scheduler** — a plain asyncio loop started in the FastAPI `lifespan`
  (no extra dependency) — polls every 60 s for due rows and runs the publish flow.
- Each attempt is recorded; failures retry up to 3 attempts, then mark `failed`.

### 5.5 Rate limits & quotas (enforce in `registry` rate limits)
- **25 API-published posts per IG account per rolling 24 h.** Hard ceiling.
- Hashtag *search* endpoint: 30 unique hashtags per 7 days — relevant if
  step 4 ever queries live hashtag volume (v1 can skip live lookup).
- The existing `ToolDef.rate_limit` / `rate_window` mechanism covers
  `publish_instagram_post` — set it to 25 / 86400 as a backstop.

---

## 6. Data model (new tables)

Added to `database.py` `init_db()`:

```sql
-- The single connected Instagram Business account. Single-account model:
-- a singleton row keyed id='primary', no owner_user_id (see §12).
CREATE TABLE ig_accounts (
    id               TEXT PRIMARY KEY,        -- always 'primary'
    ig_user_id       TEXT NOT NULL,
    fb_page_id       TEXT NOT NULL,
    username         TEXT,
    access_token     TEXT NOT NULL,           -- Fernet-encrypted
    token_expires_at TEXT,
    connected_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- A content plan = the output of the planning workflow (steps 1-6)
CREATE TABLE content_plans (
    id            TEXT PRIMARY KEY,
    owner_user_id TEXT REFERENCES users(id),  -- nullable until multi-tenancy is decided
    niche         TEXT,                       -- the chosen niche
    status        TEXT NOT NULL DEFAULT 'planning'
                  CHECK(status IN ('planning','scheduled','active')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Per-step artifacts (niche list, viral ideas, hashtags, calendar JSON, ...)
CREATE TABLE plan_artifacts (
    id          TEXT PRIMARY KEY,
    plan_id     TEXT NOT NULL REFERENCES content_plans(id),
    step        TEXT NOT NULL
                CHECK(step IN ('niche','viral','caption','hashtag','schedule','monetize')),
    content     TEXT NOT NULL,   -- markdown or JSON
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(plan_id, step)
);

-- Individual posts queued for the publishing scheduler
CREATE TABLE scheduled_posts (
    id            TEXT PRIMARY KEY,
    plan_id       TEXT REFERENCES content_plans(id),   -- nullable; ad-hoc posts allowed
    post_type     TEXT NOT NULL CHECK(post_type IN ('image','reel')),
    media_url     TEXT NOT NULL,   -- public URL Instagram will fetch
    caption       TEXT,
    scheduled_for TEXT NOT NULL,   -- UTC 'YYYY-MM-DD HH:MM:SS'
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK(status IN ('pending','publishing','published','failed','cancelled')),
    ig_media_id   TEXT,            -- set after publish
    attempts      INTEGER NOT NULL DEFAULT 0,
    last_error    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Artifacts are shared between sub-agents via `plan_artifacts`: a later step
reads earlier steps with the `read_plan_artifact` tool keyed by `plan_id`.

---

## 7. New tools

Instagram integration (Phase 3 — built):
- `backend/security/token_crypto.py` — Fernet encrypt/decrypt for tokens.
- `backend/tools/instagram_api.py` — Graph API client: OAuth URL + CSRF state,
  code→token exchange, long-lived token, resolve the Page's IG account.
- `backend/tools/instagram_accounts.py` — `ig_accounts` storage + the
  `connect_instagram` and `list_ig_accounts` registry tools.
- `backend/instagram_oauth.py` — the `/api/instagram/oauth/callback` router.

Instagram publishing (Phase 4 — built):
- `backend/tools/instagram_publish.py` — `scheduled_posts` storage + the
  `queue_post` (**HIGH risk**, §9), `list_scheduled_posts`, `cancel_scheduled_post`
  tools, and the scheduler's data layer.
- `backend/scheduler.py` — the asyncio publishing loop.
- Graph publish calls (`create_media_container`, `publish_container`, …) live in
  `instagram_api.py`.

Media pipeline (Phase 5 — built):
- `backend/tools/media_gen.py` — the media library: `save_media_asset` storage,
  `generate_post_image` (Imagen via the Gemini API), `list_media_assets`.
- `backend/media_routes.py` — the `POST /api/instagram/media` upload route.
- Media files live in `backend/media/` (gitignored), served by FastAPI in dev
  and nginx in prod.

Insights + calendar API (Phase 6 — built):
- `get_account_insights` (in `tools/instagram_accounts.py`) — live account
  metrics over a period via the Graph API, plus a queue summary.
- `backend/instagram_routes.py` — JWT-protected read-only GETs powering the
  calendar UI: `/api/instagram/account`, `/plans`, `/plans/{id}`,
  `/scheduled-posts`, `/insights`.
- `frontend/components/InstagramCalendar.tsx` — the FEED panel (account banner,
  insights last 7d, scheduled posts grouped by status); toggled from the top bar.

Hardening + polish (Phase 7 — built):
- `backend/token_refresher.py` — hourly background job that refreshes the
  long-lived IG token before expiry; wired into `lifespan` alongside the scheduler.
- `get_post_insights` tool — per-post Graph metrics (reach, likes, comments,
  saves, shares, total interactions).
- Windows console UTF-8 logging fix so emoji-bearing tool results don't crash
  the logger when piped on Windows.
- Expanded `log_redact` patterns: Google API keys, FB/IG access tokens,
  IGAA tokens, Fernet ciphertext.

`backend/tools/plan_artifacts.py` — shared planning storage (built — Phase 1):
- `create_content_plan(niche)` / `list_content_plans` / `get_content_plan(plan_id)`
- `update_content_plan(plan_id, niche, status)` — set chosen niche, advance status
- `save_plan_artifact(plan_id, step, content)` — upsert, keyed `(plan_id, step)`
- `read_plan_artifact(plan_id, step)` — returns an `exists` flag for dependency checks

`backend/agents/instagram_subagents.py` — the 6 planning sub-agent configs
(built — Phase 2).

`backend/tools/instagram_steps.py` — the 7 step tools (built — Phase 2),
`run_niche_finder` … `run_automation_setup`. Steps 1-6 spawn a sub-agent per
§4.2; `run_automation_setup` is a pure-logic readiness check (Phase 4).

All registered in `main.py` `lifespan` alongside the existing `register_*` calls.

> **Deferred — `web_search`.** Earlier drafts gave the research sub-agents a
> `web_search` tool. Phase 2 ships them **without** it — they run on model
> knowledge, which matches the original prompt set and is sufficient for
> ideation. Adding live web search later is additive: a `web_search` flag on
> `AgentConfig` that appends Anthropic's native web-search server tool to the
> `tools` list in `BaseAgent.run()`.

---

## 8. Scheduler component

`backend/scheduler.py` — a plain asyncio loop (no APScheduler), started in
`lifespan` and cancelled on shutdown:
- Every 60 s: claim `pending` rows where `scheduled_for <= datetime('now')`.
- For each: mark `publishing` → run the publish flow → mark `published` (store
  `ig_media_id`), or record the attempt — back to `pending` to retry, or `failed`
  after 3 attempts.
- Respects the **kill switch** (a `lambda` reading `_kill_switch_active`) — if
  active, the tick no-ops and leaves rows `pending`.
- Enforces Meta's **25 posts / 24 h** cap; defers the rest to a later tick.

---

## 9. Security

The platform already has the right primitives — this slots into them.

- **Approval gate:** `queue_post` is in `_HIGH_RISK` in `security/approval.py` —
  scheduling a real publish is gated, so the operator sees a
  `tool_approval_request` before any post is queued. Publishing itself is the
  scheduler's job (deterministic, not an LLM tool), gated by the kill switch.
- **Kill switch:** an active kill switch freezes the scheduler — the tick no-ops
  and leaves posts `pending` (§8).
- **Token secrecy:** access tokens Fernet-encrypted at rest; never serialized
  into API responses or tool results.
- **Rate cap:** the scheduler caps publishing at 25 posts / 24 h — a backstop
  below Meta's own ceiling.
- **Tool scoping:** per §4.3, the 6 planning sub-agents have no tools at all and
  structurally cannot publish or queue.

---

## 10. Platform integration points

**Backend** (Phases 0–6 done)
- `database.py` — `content_plans`, `plan_artifacts`, `ig_accounts`,
  `scheduled_posts`, `media_assets` tables; `agents.allowed_tools` column;
  `instagram` seed agent.
- `main.py` — registers all workflow/account/publish/media tools; includes the
  OAuth + media-upload + read-only Instagram routers; mounts `/media`; runs
  the scheduler in `lifespan`.
- `agents/base.py` — `run()` returns final text; `AgentConfig.allowed_tools`.
- `tools/registry.py` — `get_schemas(allowed)` filtering.
- `config.py` — env: `META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI`,
  `IG_TOKEN_ENC_KEY`, `MEDIA_BASE_URL`, `GEMINI_API_KEY`.

**Frontend**
- `instagram` appears in `AgentSidebar` automatically (it's a seed agent).
- Connecting an account is conversational — the `instagram` agent calls
  `connect_instagram` and shows the user the link. No separate button needed.
- Step tool calls render as normal tool-call events in `ChatWindow`.
- A FEED panel (`InstagramCalendar.tsx`) toggles from the top bar — account
  banner, 7-day insights, scheduled-posts queue (Phase 6).

---

## 11. Build phases

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0 | `run()` returns text; `allowed_tools` scoping; `get_schemas(allowed)` | done |
| 1 | `content_plans` + `plan_artifacts` tables; 6 artifact tools | done |
| 2 | `agents.allowed_tools` column; 6 planning sub-agents; 7 step tools (automation stubbed); parent `instagram` agent | done |
| 3 | OAuth connect flow, `ig_accounts`, token encryption, `connect_instagram` | done (code) — needs a Meta app to go live |
| 4 | `scheduled_posts`; publish tools; the scheduler; real `run_automation_setup` | done (code) — live publishing needs a Meta app + App Review |
| 5 | Media pipeline — upload library + Gemini image generation (`generate_post_image`) | done (code) — live image generation needs a paid Gemini plan |
| 6 | `get_account_insights` + content-calendar / queue UI | done (code) — insights need a Meta-connected account |
| 7 | Hardening + polish — Windows UTF-8 logging, expanded token redaction, long-lived token refresh, `get_post_insights` | done |

Phases 1–2 (the whole planning workflow) ship and demo **without** Meta. Phases
3–7 are code-complete; what's left are *external* gates: a Meta app + App Review
(live connect, publishing, insights), and billing on the Google AI project
(image generation — Imagen is paid-only).

---

## 12. Decisions & open questions

**Decided**
- **Account model — single shared account.** The whole Core8 instance connects
  one Instagram account; `ig_accounts` is a singleton row (`id='primary'`), no
  `owner_user_id`. Per-user multi-tenancy can be layered on later.
- **Media hosting — nginx static volume.** Post media is served from the nginx
  container already in the stack (`MEDIA_BASE_URL`).
- **Scheduler — in-process asyncio loop.** Started in the FastAPI `lifespan`; no
  APScheduler, no separate worker. Revisit if reliability demands it.

- **Media intake — media library (Phase 5).** `POST /api/instagram/media`
  uploads to the nginx volume; `generate_post_image` adds Gemini/Imagen
  generation. Both produce a `media_url` for `queue_post`.

**Still open**
- **Meta App Review** — required to publish for non-tester accounts; start the
  application early. Development mode works now for accounts added as testers.
- **Paid Gemini plan** — `generate_post_image` (Imagen) needs billing enabled on
  the Google AI project; the free tier cannot generate images.
