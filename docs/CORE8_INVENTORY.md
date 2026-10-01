# Core8 Inventory

_Audit date: 2026-10-01 · Prepared by Claude Code · Source of truth: `V1P3eR1/Core8-AI`_

This inventory lists every Core8-related application, agent system, integration and
reusable component found across the owner's connected accounts, where it lives today,
and what was (or was deliberately not) brought into this repository.

## 1. Where things were searched

| Source | Access | Result |
|---|---|---|
| GitHub `V1P3eR1/Core8-AI` | read/write | Empty before this PR (README only). Now the canonical repo. |
| GitHub `V1P3eR1/My-Goddess-Orchestra-AI` (private) | read | README only (`# My-Goddess-Orchestra-AI`, 1 commit, 2026-07-29). The real code lives on Drive. Left untouched. |
| GitHub `V1P3eR1/V1P3eR1` (profile repo) | read | Empty repository. |
| Google Drive | read | **Main source of code and docs** — see §2. |
| Notion | read | 3 strategy pages (Ecosystem OS roadmap, Agent Office business plan, Projects & Ventures). |
| Netlify | read | 2 static drag-and-drop sites (§2.4). |
| Supabase | read | 1 project, created 2026-08-30, hibernated — schema could not be read. |
| Linear | read | Team `Core8-AI` (linear.app/core8-ai), only default onboarding issues COR-1..4. |
| Lovable | read | Workspace exists, **0 projects**. |
| Vercel | read | **0 projects**. |

Nothing at any source was modified, moved or deleted.

## 2. Applications

### 2.1 Core8 Platform — `apps/core8-platform/` ✅ imported
- **Origin:** Google Drive `Core8AI/Projects/core8-ai` (last README edit 2026-05-17; code edited through ~2026-08).
- **What it is:** multi-tenant-ready, multi-agent business automation platform — chat with specialist agents over WebSocket, tool use with approval gates, CRM leads, calendar, design docs, and a full Instagram growth + publishing pipeline.
- **Stack:** Python 3.12 · FastAPI · WebSocket · aiosqlite (SQLite) · Anthropic SDK · Next.js (package.json pins `next 16.2.6`, React 19, Tailwind 4, shadcn) · nginx · docker-compose.
- **Size:** backend ~4.2k LOC Python (33 files), frontend 27 files.
- **Status:** working locally on Windows (`start-backend.ps1`, `start-frontend.ps1`); production compose file exists, no evidence of a live deployment.
- See [AGENTS_CATALOG.md](AGENTS_CATALOG.md), [ARCHITECTURE.md](ARCHITECTURE.md).

### 2.2 My Goddess Orchestra ("Yelena" / master-control) — `apps/my-goddess-orchestra/` ✅ imported (minus persona library)
- **Origin:** Google Drive `My-Goddess-Orchestra-AI/` (PLAN 2026-07-28, INTEGRATIONS + QA-REPORT 2026-07-29).
- **What it is:** a local voice (Hebrew/English) + "mission control" GUI CEO-AI that delegates to **274 specialist personas** via a `delegate_to_agent(slug, task)` tool, with an autonomy loop (step cap, kill switch).
- **Stack:** single-file FastAPI `server.py` (622 lines) · single-page `static/index.html` · Browser Web Speech API · DuckDuckGo search / trafilatura / youtube-transcript tools.
- **Census:** `master-control/census/*.md` — character sheets (name, personality, voice) per agent division.
- **Persona library (`agency-agents-main/`)**: third-party, MIT (© AgentLand Contributors), ~270+ `.md` personas. **Not copied** — only `LICENSE`, `README.md` and a file index (`PERSONA_LIBRARY_INDEX.txt`). It should be added as a pinned git submodule or fetched at setup time (see TECH_DEBT).
- **Images not imported:** `static/goddess.png`, `static/goddess-v2.png` (~1.8 MB each).

### 2.3 Core8 laptop setup package — `tools/setup/` ✅ imported (2 files)
- `README-SETUP-Core8-AI.md` (Hebrew): Claude Desktop config location, folder layout, least-privilege MCP servers (filesystem, github, playwright, memory), security checklist.
- `bootstrap-Core8-AI.ps1`: Windows bootstrap script.
- **Not imported:** `Core8-AI_Full_Package.zip` (binary), law-firm Trust/LLC questionnaires (private legal).

### 2.4 Netlify sites (not imported — no source available)
| Site | URL | Deployed | Notes |
|---|---|---|---|
| `qa-core8-ai` | https://qa-core8-ai.netlify.app | 2026-07-09, manual drop | Static, no framework/functions/git link. Same uploaded file(s) as below. |
| `clinquant-peony-4aa4fb` | https://clinquant-peony-4aa4fb.netlify.app | 2026-07-09, manual drop | Single `index.html`. |

Content could not be fetched from the audit environment (egress blocked). **Action:** owner/ChatGPT to confirm whether this is the core8-ai.com landing page and, if so, commit its `index.html` under `apps/landing/`.

### 2.5 Supabase project (not imported — nothing to import)
`V1P3eR1's Project` (ref `gsbvfhtjolctcvnzstnc`, ap-southeast-1, Postgres 17, created 2026-08-30). Hibernated; tables/extensions/advisors unknown. No edge functions. Probably empty — needs a wake-up and a re-check.

## 3. Strategy & business documents (referenced, not imported)

| Doc | Location | Key content |
|---|---|---|
| core8ai Ecosystem OS — Yelena Second Brain Roadmap | Notion (edited 2026-08-22) | 4 phases: Obsidian memory (done) → Notion tools → ElevenLabs voice (HE/RU/EN) + Higgsfield media → daily self-improvement loop. Rule: keys in local `.key` files. |
| core8ai Agent Office — Business Plan | Notion (edited 2026-09-10) | Private local "AI Agent Office": Director CEO-AI + 280+ agents in 18 divisions + 8-advisor Boardroom. BYO Anthropic key. Pricing Office $79 / Pro $179 / Managed $490 per month; white-label in Y2. |
| 04 — Projects & Ventures | Notion (edited 2026-09-26) | "Core8 AI — Active Business", domain core8-ai.com; workstreams: brand, website, agents for businesses, enterprise integration, pricing, GTM, internal AI OS. |
| Core8-AI.txt | Drive (2026-05-02) | Founder story + Hebrew slogans: "AI agents that work for you 24/7 — leads, calendar". |
| My Goddess PLAN / INTEGRATIONS / QA-REPORT | Imported under `apps/my-goddess-orchestra/master-control/` | — |

## 4. OIA and ETX — clarification

**OIA and ETX are not Core8 projects and contain no Core8 code.** They appear only as
third-party onboarding PDFs in Drive folders owned by other organizations:

- **ETX** — an Israeli digital company building business websites on a closed-code platform (AWS-hosted) plus marketing. Subsidiaries: **1click** (WhatsApp marketing software), **OIA** (CRM), **etx media** (digital agency).
- **OIA ("OIA ALL IN ONE")** — ETX's CRM: lead capture (Google/Facebook/landing pages), WhatsApp Business messaging, chatbots, automated campaigns, pipeline, commissions, Hebrew UI. www.oia.co.il.
- The acronyms are not expanded in any document found.

These PDFs are third-party proprietary material containing company contact details and
are **not** imported. They are relevant only as **competitive/feature reference** for
Core8's CRM + WhatsApp roadmap. ❓ _Decision for Lev:_ is there any ETX/OIA integration or
partnership Core8 must support? (Tracked in the PR.)

## 5. Deliberately excluded (security / privacy)

| Item | Reason |
|---|---|
| `core8-ai/backend/.env`, `.env.production`, `frontend/.env.local` | Live secrets. **Never downloaded.** |
| `core8-ai/backend/core8.db` | SQLite DB — may contain users, leads, IG tokens. |
| Google Sheet "Core8-AI" (website intake answers) | Lead/customer personal data. |
| Drive `Core8AI/Costumers/` | Customer data. |
| Law-firm questionnaires (Trust + LLC) | Private legal. |
| Notion `LEV_OS` personal pages | Personal. |
| `node_modules/`, `.next/`, `.venv/`, `__pycache__/`, `package-lock.json` | Generated / regenerable. |
| `agency-agents-main/` personas | Third-party; reference upstream instead. |
| Images (`*.svg`, `favicon.ico`, goddess PNGs) | Binary; not needed for review. Re-add if required. |

## 6. Security scan result

Run on the staged files before anything was committed:

| Tool | Result |
|---|---|
| gitleaks 8.21.2 (`detect --no-git`) | **no leaks found** |
| detect-secrets (`--all-files`) | **0 findings** |
| Manual grep (Anthropic/OpenAI/GitHub/AWS/Slack/Meta token patterns, emails, IL/US phone numbers) | Only placeholders (`sk-ant-...`, `sk-ant-your-key-here`), redaction regexes in `security/log_redact.py`, a fake test IG id in `_carousel_test.py`, and `you@company.com` placeholder. |

A `secret-scan` GitHub Action (gitleaks full history + forbidden-file check) is added so
every future PR from either agent is scanned automatically.

## 7. Reusable components (quick index)

| Component | Path | Reuse value |
|---|---|---|
| Tool registry with per-tool rate limit ("anomaly gate") | `apps/core8-platform/backend/tools/registry.py` | High — drop-in for any Claude tool-use agent |
| Approval gate (off/smart/manual + blocklist) | `.../backend/security/approval.py` | High |
| Prompt-injection detector (exists, not yet wired in) | `.../backend/security/injection_gate.py` | Medium |
| Log redaction (API keys, PATs) | `.../backend/security/log_redact.py` | High |
| JWT auth + refresh-token rotation, bcrypt, login lockout | `.../backend/security/jwt_auth.py`, `auth.py` | High |
| Fernet token encryption at rest | `.../backend/security/token_crypto.py` | High |
| Sanitized subprocess env | `.../backend/security/subprocess_env.py` | Medium |
| Streaming Claude agent loop w/ approval callback | `.../backend/agents/base.py` | High |
| In-process async scheduler w/ caps and retries | `.../backend/scheduler.py` | Medium |
| Instagram Graph API client + OAuth + token refresher | `.../backend/tools/instagram_*.py`, `instagram_oauth.py`, `token_refresher.py` | High (vertical) |
| Gemini image generation tool | `.../backend/tools/media_gen.py` | Medium |
| Orchestrator delegation loop + autonomy w/ kill switch, SSRF guard | `apps/my-goddess-orchestra/master-control/server.py` | High |
| Bilingual voice HUD (Web Speech API) | `.../master-control/static/index.html` | Medium |
| Agent character-sheet census | `.../master-control/census/` | Medium (brand/persona) |
