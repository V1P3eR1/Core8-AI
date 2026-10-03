# Tech Debt & Risks

_Audit date: 2026-10-01 · Severity: 🔴 high · 🟠 medium · 🟡 low_

## 1. Strategic

| # | Sev | Item | Recommendation |
|---|---|---|---|
| S1 | 🟡 | ~~Two disconnected agent systems~~ — **decided 2026-10-01:** keep Core8 Platform (SMB/mid-market) and My Goddess (Enterprise AI OS) as separate products. | Extract shared infrastructure only deliberately, behind stable interfaces, when a second consumer actually needs it. |
| S2 | 🔴 | Source of truth was **Google Drive folders**, not git. History, reviews and CI were missing. | This repo is now canonical. Retire Drive copies to read-only archive once this PR merges. |
| S3 | 🟠 | Positioning drift: README says "multi-agent business automation", Notion says "private local Agent Office", Projects page says "full rebrand". | One product brief in `docs/` before more feature work. |

## 2. Security

| # | Sev | Item | Where | Recommendation |
|---|---|---|---|---|
| X1 | 🔴 | **Live secrets exist in `.env`, `.env.production`, `.env.local` on Google Drive** (synced cloud folder). | Drive `core8-ai/backend`, `frontend` | Rotate Anthropic, Meta app secret, JWT secret, IG encryption key, Gemini key. Move to a secret manager / host env vars. Delete from Drive after rotation. |
| X2 | 🔴 | `core8.db` (users, bcrypt hashes, leads, encrypted IG tokens) sits in Drive. | Drive `core8-ai/backend/core8.db` | Treat as customer data; move off Drive, back up encrypted. |
| X3 | 🔴 | `NEXT_PUBLIC_BEARER_TOKEN` is a **build-time public** variable — anything in it ships to every browser. | `frontend/.env.local.example`, `docker-compose.yml`, `lib/api.ts` | Compose already passes `""` in prod; remove the legacy bearer path entirely and rely on JWT. |
| X4 | 🟠 | Leads intake Google Sheet + `Costumers/` folder hold personal data in personal Drive. | Drive | Define data-retention + access policy (Israeli Privacy Protection Law / GDPR). |
| X5 | 🟠 | My Goddess has **no auth**; safe only while bound to `127.0.0.1`. | `server.py` | Never expose publicly without adding the Core8 JWT layer. |
| X6 | 🔴 | **Injection gate is not wired in** — `security/injection_gate.py` is never imported; it is also regex-only. | `security/injection_gate.py`, `main.py` | Call it on inbound user messages and on tool results from external sources (IG comments, web). Treat as a tripwire; rely on approval gate + least privilege as the real control. |
| X8 | 🔴 | **Tool scoping only for `instagram`** — `general`, `leads`, `calendar`, `design` see all 38 tools incl. `queue_post`, `connect_instagram`. | `database.py → _AGENT_TOOL_SCOPES` | Add explicit allow-lists for every seeded agent; default custom agents to a safe read-only set. |
| X7 | 🟡 | `requirements.txt` in My Goddess uses unpinned `>=` ranges. | `master-control/requirements.txt` | Pin versions; add Dependabot. |

## 3. Code / engineering

| # | Sev | Item | Recommendation |
|---|---|---|---|
| C1 | 🟠 | **shadcn UI components missing**: `frontend/components/ui/` was empty on Drive, but code imports `button`, `dialog`, `label`, `textarea`, `scroll-area`. Frontend will not build from this repo as-is. | Re-generate with `npx shadcn add button dialog label textarea scroll-area` and commit. |
| C2 | 🟠 | `package-lock.json` not imported (transfer limit). | Run `npm install` and commit the lockfile. |
| C3 | 🟠 | Public assets not imported (`public/*.svg`, `favicon.ico`, `goddess*.png`). | Re-add from Drive in a follow-up PR (binary, no secrets). |
| C4 | 🟡 | Test coverage started: `backend/tests` (pytest, 37 tests, Business Brain + WS context) runs in the `backend-tests` CI workflow. Legacy modules (leads, calendar, design, Instagram, security/*) still lack tests. | Add tests for security/*, registry and scheduler. |
| C5 | 🟠 | SQLite + in-process scheduler = single instance only. | Fine for MVP. For SaaS move to Postgres (Supabase project already exists) and a durable job queue. |
| C6 | 🟡 | README says Next.js 15; `package.json` pins `next 16.2.6`. | Update README. |
| C7 | 🟡 | Model IDs hard-coded in several files (`claude-sonnet-4-6`, `claude-haiku-4-5-20251001`, My Goddess default `claude-sonnet-4-5`). | Centralise in config; review against current model lineup. |
| C8 | 🟡 | Windows-only start scripts (`.ps1`, `setx`). | Add cross-platform `Makefile`/scripts. |
| C9 | 🟡 | My Goddess is a single 622-line `server.py` + 134 KB `index.html` with an embedded base64 image. | Split modules; serve image as a static file. |
| C10 | 🟡 | Persona library is copied by folder, not versioned. | Add as git submodule pinned to a commit, or a setup script that fetches it. |
| C11 | 🟡 | `agents/__init__.py`, `security/__init__.py`, `tools/__init__.py` are empty — fine, noted for completeness. | — |
| C12 | 🟠 | Legacy tables (`leads`, `events`, `conversations`, `messages`, `design_docs`, IG tables) are **not tenant-scoped**; only Business Brain tables are. | Add `tenant_id` to legacy tables and scope their tools before onboarding a second client on one instance. |
| C13 | ✅ | `requirements.txt` was uninstallable (httpx 0.27.2 vs google-genai ≥0.28.1). | Fixed in CORE8-001 branch: httpx 0.28.1. |

## 4. Unknowns to resolve

- Supabase project contents (hibernated during audit).
- Netlify sites' content (egress blocked during audit) — landing page?
- Location of the Obsidian memory code (Roadmap says Phase 1 done).
- Whether `Core8-AI_Full_Package.zip` contains anything not covered here.
- Any intended ETX/OIA relationship.
