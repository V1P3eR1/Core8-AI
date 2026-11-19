# Operations

## 1. Processes

| Process | Command | Must run |
|---|---|---|
| API | `uvicorn main:app --host 127.0.0.1 --port 8000` (behind nginx/HTTPS in prod) | always |
| Worker | `python -m social.worker` | always — it is the scheduler **and** the publisher |
| Dashboard | `npm run build && npm run start` (or static hosting of the Next build) | always |

Both API and worker open the same SQLite file (`DB_PATH`). Several workers may run; claims are transactional (`UPDATE … WHERE status='pending' OR lock expired`). Lock expiry (`SOCIAL_JOB_LOCK_SECONDS`, 600 s) recovers from a crashed worker automatically.

### Scheduler deployment — "my laptop is closed"

Hostinger shared hosting cannot run a persistent Python worker. Options, cheapest first:

1. **Small VPS / container host** (Hostinger VPS, Hetzner, Fly.io, Railway): run `docker-compose.yml` from `apps/core8-platform` (API + frontend) and add a `worker` service with command `python -m social.worker`, `restart: unless-stopped`. This is the recommended path: one box, one SQLite file on a persistent volume, nginx with HTTPS (`MEDIA_BASE_URL` = the public host).
2. **Managed scheduler + stateless API**: if the API is on a platform without long-running processes, call `POST /api/social/worker/tick` from an external cron (GitHub Actions schedule, cron-job.org, a cloud scheduler) every 1–5 minutes with a service JWT. Each tick processes due jobs and publications; ticks are safe to overlap. Note: in-request ticks are limited by the request timeout — keep research feeds few, or run the research job on the VPS.
3. **Claude Code scheduled tasks / `/loop`** were used only during development. They are session-scoped and are **not** the production scheduler. No cloud scheduled task was created in this build.

What is *not* acceptable: `SOCIAL_WORKER_INPROCESS=true` on a laptop and hoping it stays open.

### Restart behaviour

- Scheduled runs are keyed `(schedule_key, run_at)` and unique → a restart never double-enqueues.
- Jobs still `running` with an expired lock are reclaimed.
- Scheduled jobs whose `run_at` is older than `SOCIAL_MISSED_JOB_GRACE_MINUTES` (180) are marked **`skipped`** with reason `missed`, shown in אוטומציות ולוגים, never run late. Retry manually with "הרץ עכשיו".
- Publications are only taken when `scheduled_for <= now`; a worker outage delays, never duplicates, them.

## 2. Backups

- Data = one SQLite file + the media directory (`SOCIAL_MEDIA_DIR`, default `backend/media/social`).
- Backup: stop nothing; use `sqlite3 core8.db ".backup 'core8-$(date +%F).db'"` (online, consistent) + `rsync` the media dir. Daily, keep 14.
- Restore: stop API + worker, replace the file + media dir, start. Approval/publication state is in the DB, so a restore from before a publish could re-queue it: check אינסטגרם וחיבורים → publications after a restore and cancel anything already live.
- `IG_TOKEN_ENC_KEY` and `JWT_SECRET` must be backed up separately (secret store). Without the Fernet key the stored Instagram token is unreadable → reconnect.

## 3. Token & credential rotation

| Secret | Rotate how | Effect |
|---|---|---|
| Instagram long-lived token | Reconnect from the dashboard (new consent) or let `token_refresher` refresh | Old token invalid; publications re-check the `token` gate at run time |
| `IG_TOKEN_ENC_KEY` | Generate new key, reconnect the account (old ciphertext cannot be migrated) | Stored token unusable until reconnected |
| `META_APP_SECRET` | Reset in the Meta app dashboard, update `.env`, restart | Existing user tokens stay valid |
| `ANTHROPIC_API_KEY` | New key in console, update `.env`, restart API + worker | — |
| `JWT_SECRET` | Change + restart | All dashboard sessions log out; signed media URLs issued before become invalid (fine) |
| `SOCIAL_MEDIA_SIGNING_KEY` | Change + restart | Outstanding media URLs invalid — don't rotate while a publication is between `container_created` and `published` |

**Credential exposure** (a key shown in chat, a log, a screenshot): revoke/regenerate it *first*, then rotate as above, then search logs (`redact()` masks known shapes but assume the worst). The previously exposed API key from an earlier conversation must be revoked and regenerated; it is not stored anywhere in this repository.

## 4. Monitoring

- Dashboard סקירה כללית: worker heartbeat (red banner when stale), failed jobs, failed publications, items needing manual review, token status.
- `GET /api/social/jobs` for a machine check; `GET /api/health` for liveness.
- Notifications: every publish/failure/manual-review/token warning is logged (`NOTIFY …`, redacted). Set `SOCIAL_NOTIFY_WEBHOOK_URL` to forward to Slack/WhatsApp bridge; payloads carry ids and titles only.
- AI spend guard: `SOCIAL_AI_DAILY_TOKEN_BUDGET` — when reached, AI jobs fail with `BudgetExceeded` and show in the jobs screen. Pricing is not assumed anywhere; budget is in tokens.

## 5. Emergency pause

- Dashboard → סקירה כללית → "השהיית חירום", or `POST /api/social/settings/emergency-pause {"active": true}`.
- Effect: new scheduling blocked, automatic mode produces nothing, queued publications are **cancelled** at the next worker tick (items → `paused`). A publication already past `publish_requested` is not interrupted (the request is already at Meta) — it finishes or goes to manual review.
- Resume: set `active:false`, then re-schedule paused items (they need a fresh approval because the schedule changed).
- The platform-wide kill switch (`/api/admin/kill-switch`) also stops the worker loop when running in-process.

## 6. Recovery from failed or uncertain publication

| State | Meaning | What to do |
|---|---|---|
| `failed`, `error_class=retryable_exhausted` | 3 transient failures (network/5xx/rate limit) | Fix cause (connectivity, Meta status), re-approve and schedule again |
| `failed`, `error_class=permanent` | Media/permission/token error from Meta | Read `last_error`, fix the asset/token, re-approve, schedule |
| `needs_manual_review` | Request sent, outcome **unknown** (timeout) or container reports PUBLISHED but media id not found | Open Instagram, check whether the post exists. Then **Resolve**: `published` + the real media id, or `failed`. Only after that re-schedule. Do not create a second publication while one is unresolved. |
| `needs_manual_review` after "reconcile" | Reconcile could not verify | Same as above |

"Reconcile" (dashboard button / `POST /publications/{id}/reconcile`) re-reads the container status and recent media by caption hash; it never re-sends `media_publish`.

## 7. Switching modes

הגדרות מותג → פרסום, or `PUT /api/social/settings/publishing`:

- `draft_only` — research and content only; approve/schedule endpoints refuse.
- `approval_required` (default) — a human approval bound to the exact version is required; worker re-validates at run time.
- `automatic` — requires `confirm_automatic: true` in the request **and** `auto.allowed_categories` + `auto.allowed_account_id`. Boundaries: `max_posts_per_day`, `window_start/end` (local), `review_topics` (fact-check flags that force a human). Items with any sensitive flag, items not in an allowed category, items outside the window or over the cap stay in `needs_review`. The system records the approval as `worker:auto` so it is auditable. Emergency pause overrides everything.

Demo mode (`demo_mode`) is a separate switch: while on, live publishing is impossible and demo records are visible. Turn it off (and clear demo data) before the first real post.
