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

**VPS (Hostinger KVM, Docker Compose project `deploy`)**: `deploy/backup.sh` copies the SQLite volume (`deploy_db_data`) with `sqlite3 .backup` and tars the media volume into `/opt/core8-backups/`, keeping 14 days. Installed in root's crontab on 2026-11-19: `30 2 * * * /opt/core8/apps/core8-platform/deploy/backup.sh >> /var/log/core8-backup.log 2>&1`. A full VM snapshot can also be taken from hPanel (one slot, overwritten each time). `.env.production` (JWT secret, Fernet key, signing keys) is **not** inside any volume — copy it off the machine once and keep it with the backups.

**Redeploy without SSH**: hPanel → VPS → Docker Manager can run a one-off `core8-ops` project (image `docker:27-cli`, mounts `/var/run/docker.sock` and `/opt/core8`) whose command is `git pull` + `docker compose -p deploy -f deploy/docker-compose.vps.yml up -d --build`. Its logs show the build and the health check. Same effect as `bash /root/install.sh` from the web terminal.

**Never edit deploy files on the VPS.** `/opt/core8` is a git checkout of `main`. A local edit to `deploy/Caddyfile` or `deploy/docker-compose.vps.yml` makes the next `git pull` abort, and the next fresh install silently drops it. Change them in a PR. If you find local edits (`git status` in `/opt/core8`), copy them to `/opt/core8-backups/local-edits/`, commit the same content via a PR, then `git checkout --` the files and pull. Two such edits from other sessions (the lead-agent route and the core8-ai.io redirect) were recovered this way on 2026-11-20/21.

**Hostnames**: Caddy serves `DOMAIN` plus any space-separated `EXTRA_DOMAINS`, each with its own automatic certificate. The frontend is built with an empty `NEXT_PUBLIC_API_URL`, so it calls the API on whatever hostname it was loaded from — no rebuild per domain, no CORS. To move to a custom domain without breaking the old address: (1) add a DNS A record for the new name → `2.25.15.153` (at Cloudflare: **DNS only**, grey cloud — proxied mode breaks large media uploads and certificate issuance); (2) redeploy with `DOMAIN=<new> EXTRA_DOMAINS=srv2179387.hstgr.cloud`. `DOMAIN` is the canonical name used for `MEDIA_BASE_URL` and the Meta OAuth redirect, so update the Meta app's redirect URI at the same time. Only add a hostname after its DNS record resolves, or Caddy retries its certificate in a loop.

**LLM health**: when a live call fails with a blocking error (account usage cap, rejected key, missing permission) the dashboard header shows **LLM: חסום** with the reason, and a banner points to the keys tab. It clears on the next successful call, on "בדוק חיבור" success, or when a new key is saved. Agents keep working on templates (labelled `mock`) meanwhile.

- Data = one SQLite file + the media directory (`SOCIAL_MEDIA_DIR`, default `backend/media/social`).
- Backup: stop nothing; use `sqlite3 core8.db ".backup 'core8-$(date +%F).db'"` (online, consistent) + `rsync` the media dir. Daily, keep 14.
- Restore: stop API + worker, replace the file + media dir, start. Approval/publication state is in the DB, so a restore from before a publish could re-queue it: check אינסטגרם וחיבורים → publications after a restore and cancel anything already live.
- `IG_TOKEN_ENC_KEY` and `JWT_SECRET` must be backed up separately (secret store). Without the Fernet key the stored Instagram token is unreadable → reconnect.

## 3. Token & credential rotation

| Secret | Rotate how | Effect |
|---|---|---|
| Instagram long-lived token | Reconnect from the dashboard (new consent) or let `token_refresher` refresh | Old token invalid; publications re-check the `token` gate at run time |
| `IG_TOKEN_ENC_KEY` | Generate new key, reconnect the account (old ciphertext cannot be migrated) | Stored token unusable until reconnected |
| `META_APP_SECRET` | Reset in the Meta app dashboard, paste the new value in **אינסטגרם וחיבורים → מפתחות** (or update `.env` and restart) | Existing user tokens stay valid |
| `ANTHROPIC_API_KEY` | New key in console.anthropic.com → paste in **אינסטגרם וחיבורים → מפתחות** ("בדוק לפני שמירה" runs an 8-token live check). No restart: API and worker reload within ~20 s. `.env` remains the fallback | — |
| `JWT_SECRET` | Change + restart | All dashboard sessions log out; signed media URLs issued before become invalid (fine) |
| `SOCIAL_MEDIA_SIGNING_KEY` | Change + restart | Outstanding media URLs invalid — don't rotate while a publication is between `container_created` and `published` |

**Credential exposure** (a key shown in chat, a log, a screenshot): revoke/regenerate it *first*, then rotate as above, then search logs (`redact()` masks known shapes but assume the worst). The previously exposed API key from an earlier conversation must be revoked and regenerated; it is not stored anywhere in this repository.

### Dashboard-managed credentials (`social/keystore.py`)

The Anthropic key and the Meta App ID/Secret can be entered in the dashboard instead of `.env.production`. They are Fernet-encrypted with `IG_TOKEN_ENC_KEY` and stored in `sm_settings` as `secret:<name>`; the API never returns a value (only the last 4 characters), audit rows carry the hint only, and `security/log_redact.py` masks the shapes in logs. Precedence: dashboard value → environment variable → mock mode. Admin role required (`GET/PUT/DELETE /api/social/secrets/{name}`, `POST /api/social/secrets/anthropic_api_key/test`). Because the ciphertext depends on `IG_TOKEN_ENC_KEY`, rotating that key invalidates stored credentials as well as the Instagram token — re-enter them.

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
