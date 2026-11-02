# Core8AI Social Manager — Implementation Checklist

_Created 2026-10-27 by Claude Code (Phase 1). Updated as phases complete._

## Decisions taken in Phase 1

| # | Decision | Why |
|---|---|---|
| D1 | Build the Social Manager **inside `apps/core8-platform`** as a new backend package `backend/social/` + a new frontend route group `frontend/app/social/`. | The repo already has a FastAPI + Next.js stack with JWT auth, Fernet token encryption, log redaction, an injection gate, and an Instagram Graph API client. The brief says "if the repository already has a suitable stack, use it" and memory says existing systems must not be rewritten. Everything new is additive; no existing table or route is modified. |
| D2 | Own tables, prefixed `sm_`. The legacy `scheduled_posts` queue and 60 s scheduler are **not** used for Social Manager publications. | Avoids double-publishing and keeps the new state machine (approval binding, reconciliation, manual review) independent. The connected Instagram account (`ig_accounts`) **is** shared. |
| D3 | Meta login path: **Instagram API with Facebook Login** (already implemented in `instagram_oauth.py` / `tools/instagram_api.py`). Scope `business_management` is dropped (not listed as required in current docs). | Lowest-risk path: code + OAuth callback already exist; Facebook Login supports insights, publishing, stories (business accounts). Trade-off: requires a Facebook Page linked to the IG professional account. Instagram Login / Unified Login documented as the alternative in `docs/META_SETUP.md`. |
| D4 | Worker = separate process `python -m social.worker` (same codebase, same SQLite file) with transactional job claims + lock expiry. Dev convenience: `SOCIAL_WORKER_INPROCESS=true` runs it inside the API process. | The brief requires web and worker to be startable separately and the production path to not depend on a laptop. |
| D5 | Providers behind adapters with explicit `mode` = `live` / `mock`: LLM (Anthropic), research (RSS feeds + Anthropic web search when a key exists), Instagram (Graph API vs. mock), media storage (local FS + signed time-limited URLs), notifications (log + optional webhook). | Local demo runs with zero paid credentials; live mode is a configuration change, not a code change. |
| D6 | Canonical business rules live in `backend/social/rules/*.md`; the Claude Code skill at `.claude/skills/core8-social-manager/` references those files instead of copying them; the runtime loads the same files into prompts. | One source of truth. |
| D7 | Carousel rendering with Pillow + libraqm (RTL shaping) and the OFL-licensed **Assistant** font bundled in `backend/social/fonts/`. | Real exportable 1080×1350 JPEGs, Hebrew RTL, proper font licence. |

## External dependencies / unknowns (need Lev)

- Meta app (App ID/Secret), Facebook Page linked to the IG professional account, app roles for Standard Access.
- Anthropic API key (LLM). Without it: mock writer/researcher output, clearly labeled.
- Public HTTPS base URL for media (`MEDIA_BASE_URL`) — Meta fetches media by URL.
- Product facts: services actually offered today, prices, customers, case studies — all treated as UNKNOWN; brand profile marks assumptions.
- Hosting target for the worker (VPS/container). Hostinger shared hosting cannot run a persistent worker.

## Phase checklist

- [x] Phase 1 — inspect repo, verify Meta + Claude Code docs, write this file
- [x] Phase 2 — schema, settings, brand profile, job engine (`jobs.py`), worker (`worker.py`), mock providers, demo seed
- [x] Phase 3 — agent modules (`agents.py`), research inbox, ideas, packages, carousel render, approvals
- [x] Phase 4 — publication state machine (`publishing.py`), Meta adapter, reconciliation, emergency pause, signed media URLs (persisted revocation, migration 2)
- [x] Phase 5 — metrics, weekly report, leads, jobs screen, inbound draft-only replies
- [x] Frontend — Hebrew RTL dashboard (`frontend/app/social/`)
- [x] Phase 6 — tests (`tests/test_social.py`), docs, CLAUDE.md + skill, verification (see STATUS.md), final report
- [x] Starter pack — real sources + original drafts from the session (`social/starter_pack.py`)

## Official references used (checked 2026-10-27)

- Instagram Platform overview (login paths, permissions, access levels, rate limits): https://developers.facebook.com/documentation/instagram-platform/overview
- Content publishing (container flow, status codes, 100 posts/24h, `content_publishing_limit`): https://developers.facebook.com/documentation/instagram-platform/content-publishing
- IG User Media reference (media specs, caption 2,200 chars, 30 hashtags, `alt_text` 1,000 chars image-only): https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media
- Changelog (`impressions` deprecated from v22.0; `alt_text` added 2025-03-24): https://developers.facebook.com/docs/instagram-platform/changelog
- Claude Code skills format: https://code.claude.com/docs/en/skills
