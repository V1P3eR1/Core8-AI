# Integrations

_Audit date: 2026-10-01 · Env var **names** only — values live outside git._

## 1. Implemented in code

| Integration | Used by | Purpose | Config (env var names) | Code |
|---|---|---|---|---|
| **Anthropic Claude API** | Core8 Platform, My Goddess | All agent reasoning | `ANTHROPIC_API_KEY`, `MASTER_MODEL` (My Goddess) | `backend/agents/base.py`, `master-control/server.py` |
| **Meta Graph API (Instagram)** | Core8 Platform | OAuth connect, publish posts/carousels, insights, long-lived token refresh | `META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI`, `IG_TOKEN_ENC_KEY`, `MEDIA_BASE_URL` | `instagram_oauth.py`, `token_refresher.py`, `tools/instagram_*.py`, `scheduler.py` |
| **Google Gemini (AI Studio)** | Core8 Platform | Post image generation | `GEMINI_API_KEY` | `tools/media_gen.py` (`google-genai`) |
| **DuckDuckGo search** (`ddgs`) | My Goddess | `web_search` tool, no key | — | `server.py` |
| **trafilatura** | My Goddess | `read_webpage` content extraction | — | `server.py` |
| **YouTube transcripts** (`youtube-transcript-api`) | My Goddess | `youtube_transcript` tool, no key | — | `server.py` |
| **Browser Web Speech API** | My Goddess, Core8 (`VoiceInput.tsx`) | STT/TTS, Hebrew/English | — | `static/index.html`, `frontend/components/VoiceInput.tsx` |

### Platform-internal config
`JWT_SECRET`, `JWT_ACCESS_TTL_MINUTES`, `JWT_REFRESH_TTL_DAYS`, `BEARER_TOKEN`, `BEARER_TOKEN_PREV`,
`DEV_MODE`, `BIND_HOST`, `BIND_PORT`, `APPROVAL_MODE`, `TOOL_BLOCKLIST`, `DB_PATH`, `DOMAIN`,
`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_BEARER_TOKEN`, `AGENCY_DIR` (My Goddess).
Templates: `apps/core8-platform/backend/.env.example`, `apps/core8-platform/frontend/.env.local.example`.

## 2. Accounts / platforms in use (no code integration yet)

| Platform | State | Notes |
|---|---|---|
| GitHub `V1P3eR1/Core8-AI` | Active | Canonical repo; shared by Claude Code and ChatGPT. |
| Netlify (team `levsho10`) | 2 static sites | Manual uploads 2026-07-09; no git link. |
| Supabase | 1 project, hibernated | Not referenced by any code. Candidate to replace SQLite. |
| Linear (`core8-ai`) | Empty | Not used; GitHub Issues chosen as the coordination layer. |
| Notion | Strategy docs | Planned "Notion sync" integration. |
| Lovable, Vercel | Connected, unused | 0 projects. |
| Domain `core8-ai.com` | Owned (per Notion) | Hosting target unknown. |

## 3. Planned (documented, not built)

| Integration | Source | Priority hint |
|---|---|---|
| **WhatsApp** (digest; WhatsApp/Telegram gateway) | Business plan; My Goddess INTEGRATIONS | High — core of the CRM pitch; OIA/1click are the local competitors |
| **Gmail / Google Calendar** | Business plan | High — Calendar Agent is currently DB-only |
| **Notion sync** (read/write, mission/decision/idea DBs) | Ecosystem OS roadmap Phase 2 | Medium |
| **ElevenLabs** voice (HE/RU/EN), STT, live calls | Roadmap Phase 3; My Goddess PLAN | Medium |
| **Higgsfield** image/video | Roadmap Phase 3 | Low/Medium |
| **Obsidian** memory vault | Roadmap Phase 1 (marked done; code not located) | ? |
| **Resemble AI** deepfake detection | My Goddess (`RESEMBLE_API_KEY`) | Low |
| **MCP servers**: filesystem, github, playwright, memory; codebase-memory-mcp; browser-harness (CDP) | `tools/setup/README-SETUP-Core8-AI.md`; INTEGRATIONS | Medium |
| **Lead sources** (Google/Facebook/landing-page forms) | Inferred from OIA feature set + intake Google Sheet | High for CRM |

## 4. Third-party content & licensing

| Item | License | Handling |
|---|---|---|
| `agency-agents` persona library | MIT © AgentLand Contributors | Keep LICENSE; reference upstream / submodule. |
| 16 repos mined for My Goddess (humanizer, loopy, defuddle, …) | Various | Only ideas/patterns re-implemented; verify licenses before copying any code. |
| ETX / OIA onboarding PDFs | Proprietary third-party | Not imported. Competitive reference only. |
