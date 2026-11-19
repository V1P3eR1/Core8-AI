# Social Manager multi-tenancy — design proposal

_Status: **proposal for Lev's review, not an approved decision.** No code is changed by this
document. Read against `main` at `1e58305` (2026-11-19). Statements are from the code unless
marked **[inferred]**. Paths are relative to `apps/core8-platform/backend/`._

## 0. Summary

The Social Manager (`social/`) is single-tenant: none of its tables has `tenant_id`, every
route is platform-admin only (`require_social_operator`, `social/routes.py`), and Instagram
lookups fall back to the internal tenant (`_account_tenant`, `social/providers/instagram.py`).
To sell it to several clients, every `sm_*` row, every file under the media directory, every job
and every public URL must belong to exactly one tenant, and code with no tenant must refuse to
run. The platform already has that pattern (CORE8-005); this proposal applies it and names the
four places the pattern does not cover: the worker, per-tenant schedules, per-tenant
settings/budgets, and the Instagram binding.

Three things found while reading that the owner should know regardless of this design:

1. **`POST /api/social/instagram/connect-url` cannot work on `main`.** `routes.py:630` calls
   `build_oauth_url()` with no argument; `tools/instagram_api.py:47` requires `tenant_id`. The
   call raises `TypeError` (not the caught `GraphAPIError`). No test covers the route. Stage 2
   fixes it; it could also be a one-line fix on its own.
2. **A new tenant would inherit Core8's own brand.** `get_setting` (`social/settings.py`) merges
   stored values over `DEFAULTS`, and `DEFAULT_BRAND` holds Core8-AI's name, owner, approved
   claims and contact details. Without a change, a client tenant with no brand row would have
   posts drafted in Core8's voice with Core8's claims.
3. **Job payloads are caller-supplied.** `POST /api/social/jobs` stores `body.payload` verbatim,
   so the tenant of a job must be a server-set column, never a payload field.

## 1. Inventory

`social/schema.py` creates **17** `sm_*` tables — the expected count. 16 hold data (15 in
migration 1, `sm_media_grants` in migration 2); the 17th, `sm_migrations`, is version
bookkeeping created in `init_social_schema` and stays global.

| Table | Purpose | Keys today | Referenced by | Proposed tenant key / uniqueness |
|---|---|---|---|---|
| `sm_settings` | JSON settings: `brand`, `publishing`, `content_mix`, `carousel_templates`, plus the `worker` heartbeat | PK `key` | — | PK `(tenant_id, key)`. The `worker` heartbeat is not tenant data: move it to a reserved system row (§3.4) |
| `sm_sources` | Research inbox | PK `id`; `url_hash` UNIQUE | `sm_ideas.source_ids` (JSON, no FK) | `tenant_id`; UNIQUE `(tenant_id, url_hash)` |
| `sm_ideas` | Content ideas | PK `id` | `sm_content_items.idea_id` (FK) | `tenant_id` |
| `sm_assets` | Media file records (`filename`, `sha256`) | PK `id` | `sm_content_items.asset_ids` / `cover_asset_id` (no FK), `sm_media_grants.asset_id` | `tenant_id`; file stored under `<media_dir>/<tenant_id>/` |
| `sm_content_items` | Drafts through published items | PK `id`; FK `idea_id` | `sm_approvals`, `sm_publications` (FK), `sm_metrics.content_item_id` (no FK) | `tenant_id` |
| `sm_approvals` | Approval bound to the exact payload | PK `id`; FK `content_item_id`; index `(content_item_id, status)` | `sm_publications.approval_id` (FK) | `tenant_id` (must equal the item's) |
| `sm_publications` | Publication state machine | PK `id`; `publication_key` UNIQUE; FKs item, approval; index `(state, scheduled_for)` | — | `tenant_id`; index `(tenant_id, state, scheduled_for)`. `publication_key` stays globally unique (it starts with the item UUID) |
| `sm_jobs` | Job executions | PK `id`; UNIQUE `(schedule_key, run_at)` where key not null; index `(status, run_at)` | `sm_ai_usage.job_id` (no FK) | `tenant_id` column (not payload); UNIQUE `(tenant_id, schedule_key, run_at)` |
| `sm_schedules` | Recurring job definitions | PK `key` | `sm_jobs.schedule_key` (no FK) | PK `(tenant_id, key)` |
| `sm_metrics` | Account/post metrics (API, manual, demo) | PK `id` | — | `tenant_id` |
| `sm_leads` | Lead tracker (personal data) | PK `id` | — | `tenant_id` |
| `sm_reports` | Weekly reports (JSON) | PK `id` | — | `tenant_id` |
| `sm_audit_log` | Audit trail | PK `id` | — | `tenant_id`, nullable only for system events (`worker_started`) |
| `sm_ai_usage` | Token usage per LLM call | PK `id` | — | `tenant_id`; budget summed per tenant |
| `sm_inbound_messages` | Comments/DMs, draft-only replies | PK `id` | — | `tenant_id` |
| `sm_media_grants` | Revocation of signed media URLs | PK `asset_id` | — | `tenant_id`; PK stays `asset_id` (UUID) |
| `sm_migrations` | Applied migration versions | PK `version` | — | none (global) |

SQLite does not enforce the declared foreign keys unless `PRAGMA foreign_keys=ON`; nothing in
`social/` turns it on **[inferred from absence]**. Tenant consistency between a child and its
parent therefore has to be enforced in queries (`WHERE tenant_id=? AND id=?`), not by FKs.

## 2. Every tenant-less access, and how the tenant will arrive

All SQL goes through `social/db.py` (`fetch_all`, `fetch_one`, `execute`, `audit`); none takes
a tenant. "Fail closed" below means: `current_tenant()` raises `TenantContextError` before any
SQL runs, and the caller gets 404 (API) or the job/publication is failed with no side effect.

| Area | Where | Today | Tenant source | Must fail closed when |
|---|---|---|---|---|
| API (66 routes on `router`) | `social/routes.py` | Admin-only; no tenant anywhere | Request access check (§3.1) | No membership → 404; role too low → 403; id from another tenant → 404, never 403 |
| Lookups by id | `content.get_item`, `media.get_asset`, `publishing.cancel_publication` / `reconcile` / `manual_resolve`, `leads.update_lead`, `reports.get_report`, inbound and job routes | `WHERE id=?` | Context | Row exists but in another tenant → behave as not found |
| Substring match | `assets_delete`: `asset_ids LIKE '%id%'` | Global scan | Context | Add `tenant_id=?`; otherwise tenant B's item can block tenant A's delete |
| Cross-row reads feeding the LLM | `agents.generate_ideas` (`sm_sources`, all `sm_ideas` titles), `agents.draft_package` (sources by id), `agents.system_prompt` (brand) | Global | Context | One tenant's sources, titles or brand must never enter another tenant's prompt |
| Settings | `settings.get_setting` / `set_setting`; `publishing._pub_settings`; `planner.propose_calendar`; `carousel_render.get_templates` | One global row per key; defaults are Core8's | Context | No `brand` row for the tenant → generation refuses (see §0.2); `publishing` defaults stay safe (`approval_required`, `demo_mode: true`) |
| Emergency pause | `publishing.set_emergency_pause` | Global flag in `publishing` | Context | Per-tenant pause; a separate platform-wide stop is still needed (§3.4) |
| Jobs | `jobs.enqueue`, `claim_due_jobs`, `run_job`, handlers `_h_*`, `_claim_specific`, `jobs_retry` | No tenant; payload from the caller | **Column `sm_jobs.tenant_id`**, set by the server at enqueue; `run_job` wraps the handler in `use_tenant(job.tenant_id)` | Job row without tenant → `failed`, handler not called |
| Schedules | `jobs.ensure_schedules`, `update_schedule`, `tick` | 5 global rows from `DEFAULT_SCHEDULES` | Row's `tenant_id`; rows created only for enabled tenants (§3.3) | Tenant not enabled → no rows, nothing enqueued |
| Worker loop | `jobs.tick`, `worker_loop`, `social/worker.py`, in-process variant in `main.py` lifespan | Claims everything | Deliberate cross-tenant claim, then `use_tenant(row.tenant_id)` per row (§3.2) | Any work outside a `use_tenant` block raises |
| `POST /worker/tick` | `routes.worker_tick` | Runs a full tick in the API process | **Platform-admin only**, or removed outside `DEV_MODE` | A tenant user must not trigger other tenants' work |
| Publishing state machine | `publishing.claim_due_publications`, `run_publication`, `gate_report`, `_credentials`, `_finalize_published`, `_revoke_grants`, `auto_schedule_candidates`, `published_last_24h` | No tenant; account from `_account_tenant()` | `sm_publications.tenant_id` → `use_tenant` | Publication, item, approval and connected account not all in the same tenant → `failed`, no Graph call |
| Instagram account | `providers/instagram.py`: `_account_tenant`, `LiveInstagramProvider.account`, `live_account_with_token` | Falls back to `INTERNAL_TENANT_ID` | `current_tenant()` only | **Delete the fallback.** No context → `TenantContextError` |
| Mock provider | `MockInstagramProvider` (process singleton, one fixed `ig_user_id`) | Shared | Keyed per tenant **[design choice]** | Otherwise `published_last_24h(account_id)` and `recent_media` mix tenants in mock mode |
| Demo seeding | `demo_data.seed_demo` / `clear_demo`; called from `main.py` lifespan when `SOCIAL_SEED_DEMO` is on | Global | Context; lifespan seeds the internal tenant only | `clear_demo` deletes with `tenant_id=?` |
| Starter pack | `starter_pack.seed_starter_pack`, CLI `python -m social.starter_pack` | Global; content is Core8's own | Platform-admin only, internal tenant only | Refuse for any other tenant |
| Metrics | `metrics.record`, `refresh_metrics`, `latest_account_metrics`, `post_metrics` | Global | Context | Insights fetched with tenant A's token are stored only under A |
| Reports | `reports.build_weekly_report`, `list_reports`, `get_report` | Aggregates every table | Context | Every sub-query filtered; a report never counts another tenant's rows |
| Leads | `leads.*`, `leads_purge` | Global | Context | Purge deletes only the caller's tenant |
| Lead webhook (public) | `routes.leads_webhook`, one shared secret `SOCIAL_LEAD_WEBHOOK_TOKEN` | Writes to the global table | **Internal tenant, hard-coded**; clients use the existing per-tenant lead forms (§3.5) | Token unset → 401 (already so). No request field may choose the tenant |
| Signed media URL (public) | `routes.media_public`; `media._sig` signs `asset_id:exp` | Asset by id | **Signed token** carries the tenant (§3.5) | Signature, tenant or asset mismatch, expiry, revocation → 404 |
| File storage | `media.save_upload`, `asset_path`, `delete_asset`; flat `<SOCIAL_MEDIA_DIR>/<asset_id>.<ext>` | Flat | `<SOCIAL_MEDIA_DIR>/<tenant_id>/<asset_id>.<ext>`, path built from context + DB row | Resolved path outside the tenant's directory → refuse |
| AI budget | `providers/llm.tokens_used_today`, `record_usage` | One global daily sum | Context | Over the tenant's budget → `BudgetExceeded` (already raised today for the global sum) |
| Notifications | `providers/notify.Notifier`, one `SOCIAL_NOTIFY_WEBHOOK_URL` | Every event to one webhook | Per-tenant setting, else log only **[design choice]** | No tenant webhook → do not post to the platform webhook with client titles |
| Audit | `db.audit`, `GET /audit` | Global | Context | Listing filtered by tenant |
| Dev hook | `POST /dev/mock-behaviour` | `DEV_MODE` only | Stays platform-admin + `DEV_MODE` | — |

## 3. Fit with the pattern already on `main`

### 3.1 What exists and how it is used

- `tenancy.use_tenant(tenant_id)` / `tenancy.current_tenant()` — a `ContextVar`.
  `current_tenant()` raises `TenantContextError` when unset. Data functions in `tools/*` call
  it for every query (`tools/instagram_accounts.py`, `tools/media_gen.py`).
- `business_brain.access.resolve_access(tenant_id, user)` — `None` for an unknown tenant or
  no membership (both become 404). Platform admins have **no** implicit access to client
  tenants; they implicitly own only `core8-internal`.
- `tenant_role(min_role)` — dependency for `/api/tenants/{tenant_id}/…` (Business Brain,
  `lead_capture.py`). `query_tenant(min_role)` — same check with `?tenant_id=`, defaulting to
  the internal tenant (`media_routes.py`, Instagram routes in `main.py`).
- Routes then run data code inside `with use_tenant(access.tenant_id):` (`media_routes.py`).
- Background: `scheduler.run_scheduler_tick` does one deliberately cross-tenant read
  (`claim_due_posts`, capped per tenant so one tenant cannot starve another), then publishes
  each group inside `use_tenant(tenant_id)`. `token_refresher` does the same.
- OAuth: `build_oauth_url(tenant_id)` binds the `state` to a tenant; the callback takes the
  tenant from `consume_oauth_state`, never from the query string.
- Media: `tools/media_gen.save_media_asset` writes to `MEDIA_DIR/<tenant_id>/`.
- Migration and no-default rule: `database.py` (§4).

**Proposed for `social/`:** `social/db.py` and every data function call `current_tenant()` and
add `tenant_id=?` to each statement; routes replace `require_social_operator` with
`query_tenant(<role>)` and set the context. `query_tenant` rather than a path change keeps the
current frontend (`frontend/lib/social-api.ts`, which sends no tenant) working for the internal
tenant; a client workspace adds `?tenant_id=`. The alternative is noted in §8.

Open technical point **[not verified]**: 66 handlers each needing a `with use_tenant(...)`
block is error-prone. A router-level dependency that sets the context once would be cleaner,
but whether a `ContextVar` set in a FastAPI dependency is visible in the handler, and reset
cleanly, must be proven by a test in stage 2. Fallback: explicit block per handler plus a test
that walks `router.routes` and fails if any route lacks the tenant dependency.

### 3.2 Background worker — not covered by the existing pattern

`scheduler.py` is single-process and its claim is a plain read. The social worker is a
separate process, may run several copies, and claims with guarded `UPDATE`s
(`claim_due_jobs`, `claim_due_publications`). Keep that; add:

- claims stay cross-tenant (the only such reads, as in `claim_due_posts`), but take at most N
  rows **per tenant** per tick, so a tenant with a backlog or a failing account cannot starve
  the others (the regression `test_tenant_regressions.py` already guards for the platform
  scheduler);
- each claimed row runs inside `use_tenant(row["tenant_id"])`; an exception in one tenant's
  row is caught per row, not per tick;
- `wait_until_ready` sleeps up to 5 × 60 s per container in live mode, inside the tick. With
  several tenants this serialises everyone behind one slow upload **[inferred]**. Stage 4
  should bound it (run publications concurrently per tenant, or move the wait to a re-claim).

### 3.3 Per-tenant schedules and enablement

There is no record of which tenants use the Social Manager. `ensure_schedules` creates rows
unconditionally. Proposed: a small `sm_tenants` table (`tenant_id` PK, `enabled`, `timezone`,
`ai_daily_token_budget`, `created_at`) written only by a platform admin. `ensure_schedules`
runs per enabled tenant; a disabled tenant keeps its data but nothing is enqueued, claimed or
published. Timezone today is one process-wide value (`scfg.timezone` → `LOCAL_TZ` in
`social/db.py`); `compute_next_run`, `local_to_utc` and `_in_window` would take the tenant's.

### 3.4 Per-tenant settings and budgets

- `sm_settings` becomes `(tenant_id, key)`. Defaults: `publishing` and `content_mix` defaults
  are neutral and may stay; `DEFAULT_BRAND` and `PILLARS` are Core8-specific and must apply to
  the internal tenant only. Other tenants start with an empty brand and generation is blocked
  until the owner fills it.
- Worker heartbeat moves out of tenant settings (reserved system row or its own table).
- Budget: `SOCIAL_AI_DAILY_TOKEN_BUDGET` becomes the default for `sm_tenants.ai_daily_token_budget`;
  an optional platform-wide ceiling stays in env.
- Platform kill switch: `main.py` passes `_is_killed` to `worker_loop` only for the in-process
  worker; the standalone `social/worker.py` has no platform-wide stop except killing the
  process. A global pause row checked each tick is needed once pause is per tenant.

### 3.5 Instagram binding and the public endpoints

- `ig_accounts` is already one row per tenant (`id = tenant_id`). Removing the
  `_account_tenant` fallback makes the Social Manager use the caller's tenant. `sm_content_items.account_id`,
  the approval binding and the `account_matches` gate already tie an item to an `ig_user_id`;
  add a check that the account row's tenant equals the item's tenant.
- Do **not** add `tenant_id` to the approval `binding_hash` formula (`approvals.compute_binding`):
  it would invalidate every existing active approval on upgrade. Tenant equality is enforced by
  the queries instead.
- The platform scheduler (`scheduled_posts`, 25/day cap) and the Social Manager
  (`sm_publications`, 100/day gate) can publish to the same tenant's account with separate
  counters. Out of scope here, but a client using both would not see a combined cap.
- Signed media URL: new shape `/api/social/media-public/{tenant_id}/{asset_id}?exp&sig`, HMAC
  over `tenant_id:asset_id:exp`; the handler enters `use_tenant(tenant_id)` only after the
  signature verifies. Old-shape URLs live at most `SOCIAL_MEDIA_URL_TTL_SECONDS` (2 h); accept
  them for the internal tenant only during one release, then remove.
- Lead webhook: the platform already has per-tenant public lead capture with consent evidence
  (`lead_capture.py`, tenant taken from the form key). Proposal: keep `/api/social/leads/webhook`
  as a legacy endpoint that writes to the internal tenant only, and do not build a second
  per-tenant public intake. Whether `sm_leads` and the platform `leads` table should merge is a
  product question (§8).

## 4. Migration of an existing single-tenant database

Mirrors `database.py`'s CORE8-005 block, expressed as `social/schema.py` migration **3** (the
module already records versions in `sm_migrations`, which gives idempotency for free).

1. **Backup first.** Reuse `backup_before_migration`'s approach: SQLite online backup next to
   the DB, mode `0600`, taken only when migration 3 is not yet recorded. Rollback = stop API and
   worker, restore the file, deploy the previous build — the same documented rollback as
   CORE8-005. The backup holds client data and must be deleted once the upgrade is verified.
2. **Add the column** to the 16 data tables as
   `tenant_id TEXT NOT NULL DEFAULT 'core8-internal'`, which backfills every existing row to
   the internal tenant, and create `ix_<table>_tenant`. Guard each `ALTER` with
   `PRAGMA table_info` so a half-applied run can be repeated.
3. **Rebuild** the tables whose keys change — `sm_settings`, `sm_schedules` (composite PK),
   `sm_sources` (`UNIQUE(tenant_id, url_hash)`), `sm_jobs` (unique index recreated) — using the
   rename/create/copy/drop sequence `database.py` uses for `design_docs`.
4. **Drop the backfill default** on all 16 tables, as `_drop_tenant_default` does, so a later
   `INSERT` that omits `tenant_id` fails instead of silently landing in the internal tenant.
   `_drop_tenant_default` is generic over a table name and could be reused directly.
5. **Fresh databases**: migration 1/2 DDL is not edited (already applied in production);
   migration 3 runs on top for both fresh and existing databases, so there is one code path.
6. **Files**: move `<SOCIAL_MEDIA_DIR>/*.{jpg,png,mp4,mov}` into `<SOCIAL_MEDIA_DIR>/core8-internal/`.
   `sm_assets.filename` stays a bare name; the directory comes from `tenant_id`. The move is
   idempotent (skip files already moved). **This step is not covered by the DB backup**; the
   media directory must be copied separately (OPERATIONS.md §2 already says to back it up).
7. **In-flight work**: migrate with the worker stopped and no publication between
   `container_created` and `published`, because signed URLs change shape (§3.5).
8. **Reversibility**: restore-from-backup is the supported rollback. A down-migration is not
   proposed: after a second tenant has data, dropping `tenant_id` would merge clients' rows.

`_needs_tenancy_migration` / `_TENANT_SCOPED_TABLES` in `database.py` are not extended; the
`sm_*` tables keep their own versioned path **[design choice — avoids coupling two migration
mechanisms]**.

## 5. Authorization model (proposed)

Roles are the existing tenant roles (`viewer` < `editor` < `owner`, `ROLE_RANK`).

| Action | viewer | editor | owner | Platform admin only |
|---|---|---|---|---|
| View overview, items, calendar, sources, ideas, assets, publications, metrics, reports, jobs, audit | ✔ | ✔ | ✔ | |
| View leads and inbound messages (personal data) | — | ✔ | ✔ | |
| Create/edit sources, ideas, drafts, assets; render carousel; run research/ideas/drafts jobs; manual metrics; draft replies | | ✔ | ✔ | |
| Edit leads; purge leads | | edit | purge | |
| Approve an item; schedule; cancel a publication; reconcile / manual resolve | | | ✔ | |
| Emergency pause **on** | | ✔ | ✔ | |
| Emergency pause **off** | | | ✔ | |
| Settings: brand, content mix, templates, schedules | | | ✔ | |
| Settings: publishing mode, `demo_mode`, automatic publishing | | | ✔ | |
| Connect / reconnect Instagram | | | ✔ | |
| Seed / clear demo data in own tenant | | | ✔ | |
| Enable a tenant, set its AI budget, starter pack, `worker/tick`, `dev/mock-behaviour`, platform-wide stop | | | | ✔ |

Notes: approval is the control that binds publication, so it sits with the owner, matching
lead-capture where consent text is owner-only. Letting an editor *stop* publishing but not
resume it is deliberate (stopping is always safe). A platform admin gets none of the tenant
columns for a client tenant without a `tenant_members` row — that is how `resolve_access`
already works and it should not be weakened for support convenience. `approved_by` and audit
`actor` already record the user's email.

## 6. Test plan

New file `tests/test_social_tenancy.py`, same shape as `tests/test_tenancy.py` (two tenants A
and B in one DB, `as_tenant` helper, `Api` users with memberships). The existing
`test_social_manager_is_admin_only` is replaced by the role tests.

**No context**
- Every public data function in `social/` (parametrised list, as
  `test_tools_refuse_without_tenant_context`) raises `TenantContextError`; includes
  `live_account_with_token` — the test that proves the internal-tenant fallback is gone.

**API**
- For each resource (source, idea, item, asset, publication, job, schedule, lead, report,
  inbound, metric, setting): A creates; B's list is empty; B's GET/PATCH/DELETE by A's id is
  404; A's row is unchanged afterwards.
- Outsider with no membership gets 404, not 403, on every route; platform admin without
  membership gets 404 on a client tenant.
- Role matrix of §5: editor cannot approve/schedule/change settings; viewer cannot read leads.
- Same source URL in A and B creates two rows (`UNIQUE(tenant_id, url_hash)`).
- B cannot attach A's asset id or idea id to its own item; B cannot approve A's item.
- A's emergency pause does not cancel or block B's queued publication, and the reverse.
- A's `demo/clear` leaves B's demo rows; A's `leads/purge` leaves B's leads.
- A route-walk test: every route on the social router carries the tenant dependency.

**Worker**
- Jobs for A and B due together: each handler observes its own `current_tenant()`; research
  for A stores sources only under A; ideas for A never read B's sources or titles.
- Publications for A and B due together (mock provider): each uses its own account and token
  (mirror of `test_scheduler_publishes_each_post_with_its_own_tenants_account`).
- A has no connected account / expired token / pause on: A's publication fails or cancels, B's
  publishes (mirror of `test_scheduler_blocked_tenant_cannot_starve_next_tenant`).
- A has more due rows than the per-tenant batch: B's row is still claimed in the same tick.
- A `sm_jobs` row with a `tenant_id` in its payload that differs from the column runs as the
  column's tenant.
- A's AI budget exhausted: A gets `BudgetExceeded`, B still runs.
- Weekly report for A counts none of B's jobs, items, leads or metrics.
- Disabled tenant: no schedule rows enqueue, nothing is claimed.

**Media URLs**
- URL signed for A's asset returns the file; the same `exp`/`sig` with B's tenant or another
  asset id is 404; expired and revoked URLs are 404 (extends
  `test_signed_media_url_expires_and_revokes`).
- Upload as A lands under `<media_dir>/A/`; B's `GET /assets/{A's id}/file` is 404.
- A crafted `filename` row cannot resolve outside the tenant directory.

**Webhook**
- Valid token: the lead is stored in the internal tenant only and is invisible to A and B.
- A body or query field named `tenant_id` is ignored; missing/unset token is 401.

**Migration** (mirror of the `test_tenancy.py` migration block)
- A pre-migration DB with rows in all 16 tables: every row ends in `core8-internal`.
- After upgrade and on a fresh DB, `INSERT` without `tenant_id` fails on all 16 tables.
- Running initialisation twice is a no-op; backup taken once, none for a fresh DB.
- Media files move once; a second run does not fail or duplicate.

## 7. Staged plan

Each stage is one PR, mergeable alone, with `python -m pytest -q` green. Stages 1–3 leave the
module admin-only on the internal tenant, so no client can be affected until stage 5.

| # | PR | Content | Risk | Independently testable by |
|---|---|---|---|---|
| 0 | Connect-URL fix (optional, tiny) | Pass the tenant to `build_oauth_url`; add a route test | Low | New test; today's behaviour is a 500 |
| 1 | Schema + migration | Migration 3, backup, media move, no-default rebuild. Data layer still writes `core8-internal` explicitly | **High** — touches production data; irreversible without the backup | Migration tests in §6; dry run on a copy of the production DB |
| 2 | Tenant-aware data layer | `social/db.py` and all data functions use `current_tenant()`; routes still admin-only but wrap in `use_tenant(INTERNAL_TENANT_ID)`; remove `_account_tenant` fallback | Medium — a missed query raises (fails closed) rather than leaks | "No context" tests; full existing `test_social.py` unchanged |
| 3 | Worker | `sm_jobs.tenant_id` usage, per-tenant claim caps, `use_tenant` per row, `sm_tenants` enablement, per-tenant schedules/timezone, system heartbeat, global stop | Medium — scheduling and concurrency | Worker tests in §6 with two tenants and the mock provider |
| 4 | Public endpoints + storage | Tenant-bound signed URLs, per-tenant media paths in code, webhook pinned to internal, per-tenant mock provider, bounded `wait_until_ready` | Medium — a mistake here is a public leak | Media and webhook tests in §6 |
| 5 | Authorization | Replace `require_social_operator` with `query_tenant` + role matrix; per-tenant settings defaults (empty brand), budgets, notifications | **High** — first point a non-admin can reach the module | API isolation + role tests in §6; route-walk test |
| 6 | Frontend | Tenant selector, `?tenant_id=` in `social-api.ts`, role-aware UI | Low for data (server enforces) | `npm run lint && npm run build`; Playwright on a local two-tenant setup |
| 7 | Docs | Update `social-manager/` docs, `ARCHITECTURE.md`, STATUS "not built" list | Low | Review |

**Cannot be verified without live Meta credentials** (all tests use `MockInstagramProvider`):
that two tenants' real tokens publish to the right accounts; that Meta fetches the new
signed-URL shape; real container timing under several tenants; token expiry/refresh per tenant
against Meta; Graph rate limits per app versus per account; and whether one Meta app can serve
several clients' accounts without App Review / Advanced Access **[not checked — needs Meta's
current documentation and the app's actual status]**. A first client should go live only after
a supervised publish on a test account in a second tenant.

### PR #36 (`feat/social-facebook-and-tracked-links`, open, not modified here)

Files it changes, and where they meet this plan:

| File in PR #36 | Conflict |
|---|---|
| `social/routes.py` (+29/−2) | **Yes — stages 2 and 5.** Both edit the imports, `SETTING_KEYS`, `settings_put`, and it adds `GET /items/{id}/tracked-links`, which needs the tenant dependency and a tenant-scoped `get_item` |
| `social/settings.py` (+4) | **Yes — stage 2/5.** Adds `DEFAULT_TRACKING` to `DEFAULTS`; the same dict is restructured for per-tenant defaults. `tracking` (landing URL, campaign) is per-tenant data |
| `social/links.py` (new) | No textual conflict; pure functions, no SQL |
| `tests/test_social_links.py` (new) | Indirect — builds on the `Social` helper in `test_social.py`, which changes when routes need a tenant (stage 5) |
| `docs/social-manager/OPERATIONS.md` (+13) | Possible — stage 7 edits the same file |

Simplest order: merge or close #36 before stage 2 starts, then treat `tracking` as one more
per-tenant setting.

## 8. Open decisions for the owner

1. **One Instagram account per tenant, or several?** Today `ig_accounts` holds exactly one per
   tenant. _Recommend: one._ Several means a new key on `ig_accounts`, account choice in every
   gate and in the UI; a client with two brands can be two tenants.
2. **AI token budget: shared or per tenant?** _Recommend: per tenant, with a platform ceiling._
   A shared budget lets one client exhaust everyone's day.
3. **Demo data per tenant?** _Recommend: yes, per tenant, off by default for new tenants;_
   automatic seeding at boot stays for the internal tenant only.
4. **Who approves and publishes for a client — the client, or Core8 staff on their behalf?**
   _Recommend: the tenant `owner` role, and Core8 staff get an explicit membership per client._
   This decides whether §5 is right; it is a commercial and liability question, not a technical one.
5. **Default publishing mode for a new client.** _Recommend: `approval_required` with
   `demo_mode` on (today's defaults); `automatic` only by the tenant owner's explicit action._
6. **Brand profile for a new tenant: empty, or prefilled from the Business Brain?** _Recommend:
   empty and blocking in the first release;_ prefill from Business Brain facts later.
7. **Content pillars and audiences** are constants written for Core8 (`PILLARS`, the
   `audience` literal in `IdeaIn`). _Recommend: per-tenant setting, seeded from today's list._
8. **Timezone per tenant?** _Recommend: yes, defaulting to `Asia/Jerusalem`;_ cheap now, awkward later.
9. **Leads: keep `sm_leads` separate from the platform `leads` table, or merge?** _Recommend:
   keep separate for this work,_ send client web leads through the existing consent-recording
   lead forms, decide the merge separately.
10. **URL style: `?tenant_id=` (as Instagram routes) or `/api/tenants/{id}/social/…` (as
    Business Brain)?** _Recommend: `?tenant_id=`_ — no frontend rewrite, internal tenant keeps working.
11. **Notifications:** one platform webhook receives every tenant's events today. _Recommend:
    per-tenant webhook setting; platform webhook gets operational failures without content titles._
12. **Is Social Manager a per-tenant entitlement the platform admin switches on (`sm_tenants`)?**
    _Recommend: yes._ It is also the natural hook for packaging, which is not decided here.
13. **Meta app model:** one Core8 Meta app for all clients, or one per client? _No
    recommendation — needs the live Meta app status and App Review facts first._

## 9. Not verified

- Nothing was executed: no tests were run and no database was migrated for this document.
- The frontend (`frontend/app/social/`) was not read beyond confirming `social-api.ts` sends no tenant.
- PR #36 was read from the API file list and patches only; it was not checked out.
- Items marked **[inferred]**, **[design choice]** or **[not verified]** above.
