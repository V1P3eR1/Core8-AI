# Architecture

_Audit date: 2026-10-01 · Describes the code as imported; not a target design._

## 1. Repository layout

```
Core8-AI/
├── apps/
│   ├── core8-platform/          # Product: multi-agent business automation (FastAPI + Next.js)
│   │   ├── backend/             #   API, agents, tools, security, scheduler
│   │   ├── frontend/            #   Next.js dashboard
│   │   ├── nginx/               #   Reverse proxy config
│   │   ├── docs/instagram-bot.md
│   │   └── docker-compose.yml
│   └── my-goddess-orchestra/    # Internal/flagship: voice CEO-AI over 274 personas
│       ├── master-control/      #   server.py + static HUD + census + plans
│       └── agency-agents-main/  #   LICENSE/README/index only (persona library is external)
├── tools/setup/                 # Windows laptop/Claude Desktop bootstrap
├── docs/                        # This audit
└── .github/workflows/secret-scan.yml
```

## 2. Core8 Platform

```
 Browser ──HTTPS──▶ nginx :443 ──▶ frontend (Next.js :3000)
                        │
                        └──/api, /ws──▶ backend (FastAPI :8000)
                                         │
             ┌───────────────────────────┼──────────────────────────────┐
             ▼                           ▼                              ▼
     security layer               agent runtime                    scheduler
  JWT auth · lockout ·        BaseAgent (Anthropic stream,      asyncio loop, 60 s tick
  headers · (inj. gate*) ·   tool-use loop, max_tokens 4096)   publishes due IG posts
  approval gate · redaction         │                            (25/24h cap, 3 retries,
             │                      ▼                             kill-switch aware)
             │               ToolRegistry.dispatch ──rate-limit──▶ tools/*
             │                      │
             ▼                      ▼
        SQLite (aiosqlite, DB_PATH=/data/core8.db)      External: Anthropic, Meta Graph API,
        agents · conversations · messages · leads ·              Google Gemini (images)
        events · design_docs · users · refresh_tokens ·
        content_plans · plan_artifacts · ig_accounts ·
        scheduled_posts · media_assets
```

### Request flow (chat)
1. Frontend logs in → `POST /api/auth/login` → JWT access (15 min) + refresh (7 d).
2. Frontend opens `WS /ws/{agent_id}`. (`security/injection_gate.py` exists but is **not called anywhere** — TECH_DEBT X6.)
3. `orchestrator.get_agent()` → `BaseAgent.run()` streams Claude output to the socket.
4. On `tool_use`: blocklist check → `needs_approval()` (APPROVAL_MODE `off|smart|manual`) →
   if HIGH-risk, the frontend shows `ApprovalModal` and the user approves/denies.
5. `ToolRegistry.dispatch` enforces per-tool rate limits, runs the handler, result is redacted
   and fed back to Claude. Messages are persisted to `conversations`/`messages`.

### HTTP API
| Method | Path | Auth |
|---|---|---|
| GET | `/api/health` | none |
| POST | `/api/auth/setup` · `/login` · `/refresh` | none (setup = first admin) |
| POST | `/api/auth/logout` · `/register` ; GET `/api/auth/me` | JWT |
| POST | `/api/admin/kill-switch` ; GET `/api/admin/security-status` | JWT |
| GET/POST | `/api/agents` | JWT |
| GET | `/api/agents/{id}/conversations`, `/api/conversations/{id}/messages` | JWT |
| WS | `/ws/{agent_id}` | token |
| GET | `/api/instagram/oauth/callback` | OAuth state |
| GET | `/api/instagram/{account,plans,plans/{id},scheduled-posts,insights}` | JWT |
| POST | `/api/instagram/media` | JWT |

### Business Brain (CORE8-001)
Tenant-scoped business-intelligence layer in `backend/business_brain/`: discovery
questionnaire (JSON-defined, adaptive) → versioned facts with provenance → AI Opportunity
Engine → AI Transformation Plan draft → role-scoped context for agents. REST API under
`/api/tenants/{tenant_id}/…` and `/api/discovery/questionnaire`. Chat sessions opened with
`/ws/{agent_id}?token=…&tenant_id=…` receive the agent's scoped Brain context as a system
block. Full design: [business-brain/DESIGN.md](business-brain/DESIGN.md).

### Multi-tenancy (CORE8-005)
One shared database; every operational row (`conversations`, `messages`, `leads`, `events`,
`design_docs`, `content_plans`, `plan_artifacts`, `ig_accounts`, `scheduled_posts`,
`media_assets`) and every Business Brain row carries `tenant_id`.
- **Tenant context is server-side** (`tenancy.py`, `contextvars`): set per WebSocket session,
  REST request (`?tenant_id=`), scheduler job and OAuth callback. Tools read it; the model can
  never pass or change it. Data functions refuse to run without a tenant in context.
- Sessions without `tenant_id` run in the **Core8 internal tenant** (`core8-internal`), which holds
  all pre-multi-tenancy data. Platform admins own it implicitly; other staff need membership.
- Instagram: one connected account per tenant; OAuth `state` is bound to the tenant that
  started the connection; the scheduler publishes each post with its own tenant's account and
  applies the 25/day cap per tenant; tokens refresh per tenant.
- Media files live under `media/<tenant_id>/` (public by unguessable URL — Instagram must fetch them).
- The only cross-tenant reads are system jobs (`claim_due_posts`, `list_accounts_for_refresh`), never tools.

### Frontend
Single page (`app/page.tsx`) with: `LoginPage`, `AgentSidebar`, `ConversationList`,
`ChatWindow`, `ApprovalModal`, `CreateAgentDialog`, `HistoryView`, `InstagramCalendar`,
`SecurityDashboard`, `VoiceInput`, `ParticleBackground`. API client in `lib/api.ts`, token
handling in `lib/auth.ts`.

## 3. My Goddess Orchestra

```
 Chrome/Edge HUD (static/index.html, Web Speech STT/TTS, HE/EN)
        │  /api/chat · /api/auto/start · /api/auto/{id} · /stop · /api/agents · /api/health
        ▼
 server.py (FastAPI, 127.0.0.1:8420)
   master_turn(): Claude tool-use loop (≤12 rounds)
     ├─ delegate_to_agent(slug, task) ─▶ sub-call with persona .md as system prompt
     ├─ web_search (ddgs) · read_webpage (trafilatura, SSRF guard) · youtube_transcript
     └─ tool results wrapped in a data-only boundary (injection defence)
   Autonomy jobs: thread per mission, step cap, stop flag, JOBS pruned to 50
        │
        ▼
 AGENCY_DIR (default ../agency-agents-main) — persona library, loaded at startup
```

No database, no auth (localhost-only by design), no persistence across restarts.

## 4. How the two systems relate

| | Core8 Platform | My Goddess |
|---|---|---|
| Product | SMB / mid-market AI transformation + managed AI workforce | Long-term Enterprise AI OS / orchestration |
| Agents | 5 deep, tool-rich vertical agents | 274 shallow persona agents, 4 tools |
| Orchestration | User picks an agent | CEO-AI delegates automatically |
| Auth / multi-user | Yes (JWT) | No |
| Persistence | SQLite | None |

**Product decision (2026-10-01, PR #1 review):** these remain **two separate products and
applications** — do not collapse My Goddess into Core8 Platform. Shared infrastructure (e.g. the
security layer, tool registry, agent runtime) may be extracted later, deliberately, behind stable
interfaces. Core8 Platform roadmap: CORE8-001 Business Brain + Discovery (#2), CORE8-002
Commercial Engine (#3).
