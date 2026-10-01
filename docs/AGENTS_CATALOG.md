# Agents Catalog

_Audit date: 2026-10-01_

Two agent systems exist today. They are **not yet connected** to each other.

## A. Core8 Platform agents (`apps/core8-platform/backend`)

User-facing agents are seeded into the `agents` table (`database.py → _SEED_AGENTS`);
users can also create custom agents via `POST /api/agents` (UI: `CreateAgentDialog.tsx`).
Each agent has `model`, `system_prompt` and an optional `allowed_tools` allow-list.

| ID | Name | Model | Purpose | Tools (allowed) |
|---|---|---|---|---|
| `general` | General Assistant | claude-sonnet-4-6 | General business helper | **all 38** (no allow-list) |
| `leads` | Lead Manager | claude-sonnet-4-6 | CRM: capture, qualify, advance leads (uses `*_lead`, `search_leads`, `add_note`) | **all 38** (no allow-list) |
| `calendar` | Calendar Agent | claude-sonnet-4-6 | Meetings & scheduling — internal DB, not Google Calendar (uses `*_event`, `find_free_slot`) | **all 38** (no allow-list) |
| `design` | Head of Design | claude-sonnet-4-6 | 7-tier design workflow: briefs, specs, mockups (uses `*_design_doc`, `create_feature_spec`) | **all 38** (no allow-list) |
| `instagram` | Instagram Growth Agent | claude-sonnet-4-6 | 7-step IG theme-page growth plan + publishing | 21 scoped tools (`_AGENT_TOOL_SCOPES`) |

> Only `instagram` is scoped (`database.py → _AGENT_TOOL_SCOPES`). The other seeded agents can call every tool, including Instagram publishing — see TECH_DEBT X8.

### Business Brain context scopes (CORE8-001)
When a chat is opened for a tenant, each agent receives only its scope of the Business Brain
(`business_brain/context.py`); tenant owners can override per agent, never above
`confidential`.

| Agent | Categories | Domains | Max sensitivity |
|---|---|---|---|
| `general` | profile, products, personas, tone, goals | general | internal |
| `leads` | profile, products, personas, tone, processes, KPIs, policies, approvals, systems, pains, goals | general, sales_crm | confidential |
| `calendar` | profile, tone, processes, policies, approvals, systems | general, email_calendar, office_admin | internal |
| `design` | profile, products, personas, tone, goals | general, marketing_social | internal |
| `instagram` | profile, products, personas, tone, goals, KPIs, processes, approvals | general, marketing_social | internal |
| any other | organization profile, products, tone | general | internal |

The Opportunity Engine also recommends **planned** agent roles that don't exist yet:
`support`, `office_admin`, `operations`, `finance_ops`, `hr`, `bi_reporting`, `knowledge`,
`integrations`, `compliance`.

### Instagram sub-agents (internal, not user-facing)
Defined in `agents/instagram_subagents.py`; spawned by step tools in `tools/instagram_steps.py`.
Pure generation (`allowed_tools=[]`) — the step tool performs all side effects.

| Step | Sub-agent | Model |
|---|---|---|
| 1 `run_niche_finder` | Niche Finder | Sonnet 4.6 |
| 2 `run_viral_blueprint` | Viral Content Blueprint | Sonnet 4.6 |
| 3 `run_caption_generator` | Caption Generator | Haiku 4.5 |
| 4 `run_hashtag_formula` | Hashtag & Hook Formula | Haiku 4.5 |
| 5 `run_content_schedule` | Content Schedule | Sonnet 4.6 |
| 6 `run_monetization_map` | Monetization Map | Sonnet 4.6 |
| 7 `run_automation_setup` | — (guarded stub; live publishing via `queue_post` + scheduler) | — |

Full design: `apps/core8-platform/docs/instagram-bot.md`.

### Registered tools (38)
`add_note`, `cancel_scheduled_post`, `connect_instagram`, `create_content_plan`, `create_event`,
`create_feature_spec`, `create_lead`, `delete_design_doc`, `delete_event`, `find_free_slot`,
`generate_post_image`, `get_account_insights`, `get_content_plan`, `get_lead`, `get_post_insights`,
`list_content_plans`, `list_design_docs`, `list_design_projects`, `list_events`, `list_ig_accounts`,
`list_leads`, `list_media_assets`, `list_scheduled_posts`, `queue_post`, `read_design_doc`,
`read_plan_artifact`, `run_automation_setup`, `run_caption_generator`, `run_content_schedule`,
`run_hashtag_formula`, `run_monetization_map`, `run_niche_finder`, `run_viral_blueprint`,
`save_plan_artifact`, `search_leads`, `update_content_plan`, `update_event`, `update_lead`,
`write_design_doc`.

## B. My Goddess Orchestra (`apps/my-goddess-orchestra/master-control`)

| Role | Description |
|---|---|
| **My Goddess** (CEO / "Yelena") | Orchestrator. Default model `claude-sonnet-4-5` (`MASTER_MODEL` env). Gets a roster index of all agents; answers directly or calls `delegate_to_agent(slug, task)`. Max 12 tool rounds per turn. |
| **274 specialists** | Each runs as a Claude sub-call with its persona `.md` as system prompt. 269 from the third-party `agency-agents` library + 5 custom (below). |
| **Autonomy mode** | Goal + step budget (default 10, max 40), stop button, audit log, acceptance checks. |

### Built-in tools (orchestrator)
`delegate_to_agent`, `web_search` (DuckDuckGo), `read_webpage` (trafilatura, SSRF-guarded), `youtube_transcript`.

### Custom agents added by Core8 (2026-07-29)
| Agent | Division | Source idea |
|---|---|---|
| UI Polish Critic | design | make-interfaces-feel-better |
| Prose Humanizer | marketing | humanizer |
| Media Forensics Analyst | security | detect-skill (Resemble) — needs `RESEMBLE_API_KEY` for full power |
| Requirements Interrogator | product | Matt Pocock "grilling" skill |
| Loop Doctor | specialized | loopy (bounded-loop pattern) |

### Divisions (persona library)
academic, design, engineering (largest, ~58), finance, game-development, gis, healthcare,
marketing, paid-media, product, project-management, sales, security, spatial-computing,
specialized, support, testing, + integrations. Per-division counts in
`apps/my-goddess-orchestra/agency-agents-main/PERSONA_LIBRARY_INDEX.txt`; character sheets in
`master-control/census/`.

Notable personas for the Core8 roadmap: `engineering-multi-agent-systems-architect`,
`engineering-rag-pipeline-engineer`, `specialized-mcp-builder`, `agents-orchestrator`.

## C. Planned / documented only (no code yet)

| Agent / capability | Where documented |
|---|---|
| "Director" CEO-AI + 8-advisor **Boardroom**, 280+ agents in 18 divisions | Notion — Agent Office Business Plan |
| WhatsApp digest / WhatsApp+Telegram gateway | Notion business plan; My Goddess INTEGRATIONS (from hermes-agent) |
| Notion sync, Gmail/Calendar integration pack | Notion business plan |
| ElevenLabs voice (HE/RU/EN), STT, live calls | Notion Ecosystem OS roadmap |
| Higgsfield image/video generation | Notion Ecosystem OS roadmap |
| Obsidian second-brain memory (remember/recall/journal) | Notion roadmap — marked done, **code not found** |
| browser-harness, codebase-memory-mcp, Kanban mission board, OpenMontage video division | My Goddess INTEGRATIONS "next wave" |
