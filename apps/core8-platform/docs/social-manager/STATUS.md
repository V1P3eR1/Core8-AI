# Status — Core8AI Social Manager

_Build session: 2026-10-27 (Claude Code, cloud sandbox without outbound internet for the app itself)._

## Implemented and verified (mock providers, automated tests)

| Capability | Where | Verified by |
|---|---|---|
| Schema + versioned migrations (`sm_*`, 15 tables) | `social/schema.py` | boots on fresh and existing DBs (test suite) |
| Brand / publishing / content-mix settings, demo seed & clear | `social/settings.py`, `demo_data.py` | `test_demo_flow_research_to_report` |
| Research inbox: RSS parsing, dedupe by normalised URL, injection gate, source fields | `providers/research.py`, `agents.run_research` | `test_research_preserves_sources…`, `test_injection_in_source…` |
| Ideas, drafts (reel/carousel/image/story), producer checklist, fact checker | `agents.py`, `fact_check.py` | demo flow test, auto-mode flag test |
| Carousel rendering 1080×1350 RTL, templates, preview | `carousel_render.py` | demo flow test (spec check ok on every slide); visual check of rendered JPEG |
| Approval binding + invalidation on any publication-relevant change | `approvals.py`, `content.update_item` | 6 tests (caption, schedule, account, settings, asset id, asset bytes) |
| Publisher gates, state machine, transactional claims, unique publication key, retry/backoff, permanent failure, timeout → reconcile → manual review, manual resolve | `publishing.py` | 10 tests |
| Three modes + automatic boundaries + explicit confirmation | `publishing.py`, `routes.py` | 3 tests |
| Emergency pause | `publishing.set_emergency_pause` | `test_emergency_pause_blocks_scheduled_publishing` |
| Jobs, schedules (Asia/Jerusalem, DST), idempotent scheduled runs, concurrent claims, missed-job skip, heartbeat | `jobs.py`, `worker.py` | 6 tests incl. DST transitions 2026 |
| Signed time-limited media URLs + persisted revocation | `media.py`, `routes.media_public` | `test_signed_media_url_expires_and_revokes` |
| Metrics store (api/manual/demo), weekly report with missing-metrics list and observation≠recommendation | `metrics.py`, `reports.py` | demo flow test |
| Leads CRUD + retention purge; inbound draft-only replies | `leads.py`, `routes.py` | 2 tests |
| Secrets never in API/audit; redaction of Meta/Anthropic/JWT shapes | `security/log_redact.py` | 3 tests (bundle scan skips if frontend not built) |
| Hebrew RTL dashboard (12 sections) | `frontend/app/social/` | `npm run lint`, `npm run build` (see final report) |

Test run: `cd backend && python -m pytest -q` → **81 passed, 1 skipped** (the skip is the client-bundle scan, which runs once the frontend is built).

## Implemented but awaiting credentials / your machine

| Item | Needs |
|---|---|
| Live RSS research | Outbound internet (works on your machine; `SOCIAL_RESEARCH_MODE=auto`) |
| Claude-written research analysis, ideas, packages, reply drafts | `ANTHROPIC_API_KEY` |
| Instagram connect, container/publish flow, insights, publishing limit, token refresh | Meta app + Page-linked Business account; `SOCIAL_INSTAGRAM_MODE=live`; public `MEDIA_BASE_URL` |
| Story publishing, `is_ai_generated` label, Story `link_clicks` metric | Live account (business type) to verify |
| Webhook notifications | `SOCIAL_NOTIFY_WEBHOOK_URL` |
| Video duration/codec validation | `ffprobe` installed on the host |

Everything in this table is **unverified** against real services. The code paths exist and are exercised by mocks only.

## Not implemented

- Comments/DMs ingestion from Meta (needs `instagram_manage_comments` / `instagram_manage_messages`; not requested). Manual import + draft replies only. Outbound replies disabled by design.
- Image/video generation providers. Reels and single images need uploaded assets; carousels are rendered locally.
- Multi-account / multi-tenant. One connected Instagram account per instance (platform design).
- Hashtag/competitor research on Instagram itself (would require Advanced Access and is out of scope for the MVP).
- Dashboard authentication beyond the platform's JWT (no SSO/2FA).

## Known risks & next actions

1. **Graph API version sunset**: `tools/instagram_api.py` pins v21.0 (OAuth) and `social/providers/instagram.py` v22.0. v21 is removed 2027-01-21 — bump before then.
2. **Unified Login**: Meta recommends it for new integrations; migrate the OAuth module if the Facebook-Login path causes friction with your Page setup.
3. **SQLite + two processes**: fine for one owner; move to Postgres if several operators or workers are added.
4. **Media exposure window**: 2 h signed URLs; revoke happens at publication end. Keep private material out of assets.
5. **Mock-only verification**: the first live publication must be a low-risk image post, watched end to end (see META_SETUP §8).
6. **Legacy scheduler** (`scheduler.py`, `scheduled_posts`) still runs in the API process for the older Instagram tools; it does not touch `sm_*` tables. Consider disabling it once the Social Manager is the only publisher to avoid confusion.
7. **Previously exposed API key** (from an earlier chat): revoke and regenerate; nothing in this repo stores it.
