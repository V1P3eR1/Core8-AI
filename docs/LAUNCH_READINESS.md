# Launch Readiness — Security Gate (issue #11)

_Last verified: 2026-11-12 · Branch `fix/core8-011-security-gate` (stacked on PR #8)_
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
| 8 | Checks re-run, risks documented | ✅ | This document. 98 backend tests pass; gitleaks / detect-secrets clean. |

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
python -m pytest -q                      # 98 tests, incl. tests/test_security_gate.py, tests/test_tenancy.py
gitleaks detect --source . --log-opts="--all" --redact
git grep -nIiE 'NEXT_PUBLIC_[A-Z0-9_]*(TOKEN|SECRET|KEY|PASSWORD|PRIVATE|CREDENTIAL)' -- ':!*.md'   # must be empty
```
