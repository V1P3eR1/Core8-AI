# Launch Readiness — Security Gate (issue #11) and Launch Audit (issue #10)

_Last verified: 2026-11-12 · §1–6: branch `fix/core8-011-security-gate` (PR #13, stacked on PR #8) · §7–11: branch `feat/core8-010-launch-readiness` (stacked on PR #13)_
_Status legend: ✅ done & tested · 🟡 done, needs Lev's action · 🔴 open blocker_

**Bottom line:** do **not** expose the platform publicly or onboard a second client until the 🔴
items below are closed and PR #8 + this PR are merged.

## 1. Gate checklist

| # | Item (issue #11) | Status | Evidence |
|---|---|---|---|
| 1 | Production secrets / customer DB copies in cloud-synced folders | 🟡 | Still present in Google Drive (§2). All are **private** (not link-shared). Needs rotation + removal by Lev. |
| 2 | Rotation checklist for exposed tokens | 🟡 | §3. Not rotated — requires Lev in provider consoles. |
| 3 | No credentials in the browser bundle | ✅ | `NEXT_PUBLIC_BEARER_TOKEN` removed from frontend code, Dockerfile, compose and example. Legacy shared bearer accepted only with `DEV_MODE=true`. CI job `no-browser-secrets` + test block any secret-shaped `NEXT_PUBLIC_*`. |
| 4 | Seeded agent tool scopes: deny-by-default, least privilege | ✅ | Every agent has an explicit allow-list; agents/custom agents without one get **no tools**; a tool outside the list is refused at run time even if the model names it. Every tool has a risk class (`security/tool_policy.py`), enforced by test. |
| 5 | Injection safeguards + human approval for sensitive actions | ✅ (partial by design) | Tool output with outside content is wrapped as untrusted data and scanned; a flagged result makes every later side-effecting call in that run require approval. **External actions (publish, Instagram connect, paid generation) always need human approval — even with `APPROVAL_MODE=off`**; with no approver connected they are refused. Regex detection is a tripwire, not a defence on its own (§5). End-to-end WebSocket tests show an external call (`queue_post`) never runs when the operator denies it, when the approval goes unanswered (fail-closed timeout), or when the answer is not a literal `true`, in every approval mode; it runs only after an explicit approval. These tests found and fixed a bug: approval answers were queued behind the waiting agent and never delivered, so every approval timed out (fail-closed, but approvals could not work). |
| 6 | My Goddess localhost-only | ✅ | `server.py` binds `127.0.0.1:8420`, no `0.0.0.0`; regression test. No auth, so it must never be exposed. |
| 7 | Tenant isolation of leads, messages, conversations, tools | 🟡 / 🔴 | ✅ Core platform: PR #8 (CORE8-005) — awaiting review. 🔴 **PR #9 Social Manager** adds 17 `sm_*` tables with **no tenant scoping** (§4). |
| 8 | Checks re-run, risks documented | ✅ | This document. 98 backend tests pass on PR #13 (121 with the lead-capture tests in §9); gitleaks / detect-secrets clean. |

## 2. Secrets & customer data in cloud-synced storage (names and locations only)

Verified via Google Drive metadata on 2026-11-12. **No file contents were read.**

| File | Location (Drive) | Visibility | Last modified | Contains (by name/convention) |
|---|---|---|---|---|
| `.env` | `Core8AI/Projects/core8-ai/backend/` | private | 2026-05-19 | backend secrets (Anthropic, JWT, Meta, IG encryption, Gemini — key names per `.env.example`) |
| `.env.production` | same folder | private | 2026-05-17 | production backend secrets |
| `.env.local` | `…/core8-ai/frontend/` | private | 2026-05-17 | frontend env (historically `NEXT_PUBLIC_BEARER_TOKEN`) |
| `core8.db` | `…/core8-ai/backend/` | private | 2026-05-21 | users (bcrypt hashes), leads, encrypted IG tokens |
| Google Sheet "Core8-AI" | My Drive | private | 2026-07-09 | website-intake lead answers (personal data) |

Being private limits exposure, but synced folders replicate secrets to every signed-in device and
to Google's storage. Treat them as exposed.

## 3. Rotation checklist (Lev — in each provider's console; Claude Code must not rotate live keys)

Order matters: create new → deploy new → verify → revoke old → delete Drive copies.

- [ ] **Anthropic API key** — console.anthropic.com → API Keys: create a new key with a spend limit; revoke the old one.
- [ ] **Meta app secret** (`META_APP_SECRET`) — developers.facebook.com → App → Settings → Basic → Reset secret.
- [ ] **Instagram encryption key** (`IG_TOKEN_ENC_KEY`) — generate a new Fernet key; existing encrypted tokens become unreadable → reconnect Instagram per tenant after rotation (planned, short outage).
- [ ] **Instagram long-lived tokens** — reconnect via `connect_instagram` (issues fresh tokens).
- [ ] **JWT secret** (`JWT_SECRET`) — new random ≥32 chars; all sessions are logged out (expected).
- [ ] **Legacy `BEARER_TOKEN`** — set a new value only if `DEV_MODE` is used; leave empty in production.
- [ ] **Gemini API key** — aistudio.google.com → API keys: create new, delete old.
- [ ] Store the new values only in the host's secret manager / environment, **not** in Drive.
- [ ] Delete the Drive copies in §2 (or move `core8.db` to encrypted, access-controlled backup storage).
- [ ] Confirm `gitleaks` stays clean (no secret ever reached git — verified).

## 4. Tenant isolation status

| Area | Status |
|---|---|
| Business Brain (CORE8-001) | ✅ merged, tenant-scoped, tested |
| Leads, events, conversations, messages, design docs, plans, IG accounts, posts, media (CORE8-005) | ✅ implemented in **PR #8**, 23 isolation tests, mutation-checked — **awaiting review/merge** |
| **Social Manager (PR #9)** | 🔴 17 new tables (`sm_settings`, `sm_ideas`, `sm_content_items`, `sm_leads`, `sm_inbound_messages`, `sm_publications`, …) with **no `tenant_id`**; also re-introduces `NEXT_PUBLIC_BEARER_TOKEN` (inherited from the older base). Must be tenant-scoped, or explicitly restricted to the Core8 internal tenant, before merge. |

## 5. Residual risks (accepted for now, tracked)

| Risk | Mitigation in place | Next step |
|---|---|---|
| Prompt injection that evades regex detection | Untrusted framing of tool output; least-privilege tools; external actions always need approval; flagged content escalates approvals | Model-based classifier or dual-LLM pattern for inbound content (WhatsApp/IG DMs) before those channels launch |
| Writes (create/update lead, event, doc) run without approval in `smart` mode | They are internal and tenant-scoped; deletes need approval; any flagged content in the run forces approval | Revisit per customer contract (some may want `manual`) |
| Media files are public by unguessable URL | Required for Instagram to fetch; UUID names under `media/<tenant>/` | Signed, expiring URLs when moving to object storage |
| SQLite, single instance | Tenant filters in code + tests | Postgres with row-level security (TECH_DEBT C5) |
| Custom agents now have no tools by default | Deliberate (deny by default) | Admin UI/API to grant a vetted tool list per custom agent |

## 6. How to reproduce

```bash
cd apps/core8-platform/backend
pip install -r requirements-dev.txt
python -m pytest -q                      # 121 tests, incl. test_security_gate, test_tenancy, test_lead_capture
gitleaks detect --source . --log-opts="--all" --redact
git grep -nIiE 'NEXT_PUBLIC_[A-Z0-9_]*(TOKEN|SECRET|KEY|PASSWORD|PRIVATE|CREDENTIAL)' -- ':!*.md'   # must be empty
```

---

# Launch audit (issue #10)

## 7. Top 5 launch blockers

| # | Blocker | Severity | Owner | What closes it |
|---|---|---|---|---|
| 1 | Production secrets and the customer DB still sit in Google Drive; keys not rotated (§2–3) | 🔴 Critical | **Lev** | Rotation checklist §3, then delete the Drive copies |
| 2 | Tenant isolation (PR #8) and the security gate (PR #13) are not merged | 🔴 Critical | Review → Lev / ChatGPT | Review and merge #8, then #13, then this PR |
| 3 | No production hosting for the platform: `core8-ai.com` is not attached to either Netlify site, `nginx.conf` still has `YOUR_DOMAIN`, no deploy pipeline, no DB backups, SQLite single instance | 🔴 High | Lev (where to host) → Claude Code (deploy config) | Choose a host (VPS + docker compose as in the repo, or a managed platform); then TLS, backups and a staging deploy |
| 4 | Website → CRM lead path did not exist (intake went to a Google Sheet holding personal data, outside the tenant model) | 🟡 High | Claude Code (this PR) + Lev / ChatGPT (consent text, privacy policy) | §9 endpoint (this PR); legal consent text and privacy policy; wire the landing-page form to it |
| 5 | PR #9 Social Manager: 17 `sm_*` tables with no `tenant_id`, re-introduces `NEXT_PUBLIC_BEARER_TOKEN` | 🟡 High (blocks #9 only) | **Lev** decides (a)/(b) on PR #9 | Tenant-scope it, or restrict it to the Core8 internal tenant |

Not blocking, but before real customers: frontend lint errors (§10), no frontend tests or
frontend CI build, in-process rate limits (one backend instance only), no error monitoring.

## 8. Inventory (Core8 Platform, at this branch)

| Area | State |
|---|---|
| Backend routes | 56 (incl. `/docs`, `/redoc`, `/openapi.json`): tenants & Business Brain 27, Instagram 7, auth 6, admin 3, agents 3, discovery 1, conversations 1, media 1, health 1, **public lead form 1**, WebSocket 1 |
| Public (unauthenticated) routes | `GET /api/health`, `POST /api/auth/setup` (first admin only), `/login`, `/refresh`, Instagram OAuth callback (state-bound), `POST /api/public/lead-forms/{key}/submit`, `/media/*` (unguessable names), FastAPI docs |
| Backend tests | 121 (pytest): business brain API, questionnaire, tenancy, security gate, lead capture, WS context |
| Migrations | No migration tool: `database.init_db()` + `business_brain/schema.py` + `lead_capture.py` create tables idempotently at startup; `tenant_id` columns are added to legacy tables in place (PR #8). Alembic or similar is needed before Postgres (TECH_DEBT C5) |
| Env templates | `backend/.env.example` (no real values), `frontend/.env.local.example` (only `NEXT_PUBLIC_API_URL`) |
| Deploy config | `docker-compose.yml` (backend, frontend, nginx; backend only on the internal network), `backend/Dockerfile`, `frontend/Dockerfile`, `nginx/nginx.conf` (placeholder domain, Let's Encrypt path) |
| CI | `secret-scan` (gitleaks + detect-secrets + `no-browser-secrets`), `backend-tests`. **No frontend build or lint in CI** |
| Hosting found (read-only check) | Netlify team: `qa-core8-ai` and `clinquant-peony-4aa4fb`, both on `*.netlify.app`, no custom domain, Netlify Forms disabled. `core8-ai.com` could not be fetched from this container (egress blocked), so its DNS target is **unverified**. Nothing was changed |

## 9. Safe lead-capture workflow (implemented in this PR)

```
landing page form ──POST /api/public/lead-forms/{form_key}/submit──▶ backend
                                                      │ form_key → tenant (server-side)
                                                      ▼
                     origin check → rate limit → honeypot → validation → consent
                                                      ▼
                     leads (tenant_id, source="web-form:<form>")  +  lead_consents
                                                      ▼
                     agents read it only via list/search/get_lead → wrapped as untrusted
```

| Requirement | How |
|---|---|
| Tenant isolation | A tenant **owner** creates a form (`POST /api/tenants/{id}/lead-forms`) and gets a random `form_key`. The public request never names a tenant; unknown fields are rejected (422) |
| Consent | `consent: true` is mandatory; stored in `lead_consents` with the tenant's consent-text version, time, and an HMAC of the IP (no raw IP) |
| Validation | Name 1–120, email format, phone format, company ≤120, message ≤2000, control characters stripped; email **or** phone required |
| Anti-spam | Honeypot field `website` (silently dropped, same 202), 5 submissions per IP per form per 10 min, 200 per form per hour, optional allowed-origins list per form |
| Spoofing | Client IP comes from the socket; proxy headers only with `TRUST_PROXY_HEADERS=true` and then only the proxy-written value (`X-Real-IP` / last `X-Forwarded-For` hop). The login rate limiter used to trust the forgeable first hop — fixed in this PR |
| Secure storage | Same tenant-scoped `leads` table as the CRM; no new copy in Sheets/Drive. Lead and consent row are written in **one transaction** — a failure rolls both back (failure-injection test), so no lead exists without its consent record |
| Logs | Form key and outcome only, never name/email/message (tested) |
| Prompt injection | Lead text is outside content: lead tools are in `UNTRUSTED_OUTPUT_TOOLS`, so a flagged note forces approval for later side effects (§1 item 5) |
| Revocation | `DELETE /api/tenants/{id}/lead-forms/{key}` disables a form (404 afterwards) |
| Browser access | Add the landing-page origin to `CORS_EXTRA_ORIGINS`, or post server-side (e.g. a Netlify function) |
| Origin check — scope | **Not a bot or authentication control.** Any script can forge or omit `Origin`. It only stops *other websites* from posting through visitors' browsers. With an allow-list set, a missing `Origin` is rejected; for server-to-server posting leave the list empty. Spam control is the rate limits + honeypot, tested with no Origin and no allow-list |
| Rate-limiter memory | Bounded: at most `MAX_TRACKED_KEYS` (20 000) keys, expired keys pruned and least-recently-used evicted. Keys are only created for existing, enabled forms, after the per-form limit |
| Proxy trust | `TRUST_PROXY_HEADERS=true` is safe only when (a) the backend is reachable **only** through our nginx and (b) nginx overwrites `X-Real-IP` with `$remote_addr`. Both are true in the repo's `docker-compose.yml` / `nginx.conf` and checked by a test. Any other deployment (managed platform, extra CDN) must re-verify this before enabling it |

**Residual risks (accepted until stated):**
- Rate limits are per process and reset on restart; a multi-instance deployment needs a shared limiter (e.g. Redis) or limits at the proxy/CDN (`limit_req` in nginx). Required before scaling out.
- A distributed botnet with many IPs is limited only by the per-form cap (200/h) — enough to keep the CRM usable, not to keep spam out. Add a CAPTCHA/Turnstile if spam appears.
- Evicting the least-recently-used key under extreme load can reset that key's counter; the per-form cap still applies.

**Merge order and evidence:** #8 → #13 → #14. Test and secret-scan results here are for this branch's head only. After #8 and #13 merge, this branch must be updated onto that `main` and CI re-run on the resulting head before #14 is merged.

**Still needed before switching the website over (not code):** consent wording and privacy
policy in EN/HE/RU (Lev, with ChatGPT drafting), and the decision on what happens to the existing
leads in the "Core8-AI" Google Sheet (move into the internal tenant, or delete). Moving
customer data needs Lev's separate approval.

## 10. Build, lint and test commands (run 2026-11-12)

| Command (from `apps/core8-platform`) | Result |
|---|---|
| `cd backend && pip install -r requirements-dev.txt && python -m pytest -q` | ✅ 121 passed |
| `cd frontend && npm ci` | ✅ (uses the `package-lock.json` added in this PR, identical to PR #9's) |
| `cd frontend && npx next build` | ✅ after adding the missing `components/ui/*` (shadcn) and `types/speech-recognition.d.ts`, the same files as PR #9. Before: build failed on missing imports |
| `cd frontend && npx eslint .` | ❌ 8 errors, 2 warnings, all existing code: `react-hooks/set-state-in-effect` (data loading in `useEffect` in `SecurityDashboard`, `InstagramCalendar` and others), `prefer-const` (`ParticleBackground`), `react-hooks/refs`, 2× `exhaustive-deps`. Not runtime bugs; fix when the frontend is reworked, then add frontend lint/build to CI |
| `gitleaks detect --source . --log-opts="--all" --redact` | ✅ no leaks |

## 11. Who does what (issue #10)

- **Claude Code (this PR):** inventory, commands, blockers, lead-capture endpoint, proxy-IP fix.
- **ChatGPT:** landing-page copy and the LEV brand brief (per issue #10); draft consent text and privacy policy for Lev's review.
- **Lev:** blockers 1, 3 (hosting choice) and 5; approve consent text; decide on the Google Sheet leads.
