# Core8 Business Brain + Smart Discovery — Design (CORE8-001)

_Status: v1 implemented in `apps/core8-platform/backend/business_brain/` · Issue #2_

The Business Brain is the governed, versioned, tenant-scoped model of a client's business.
Discovery fills it; the Opportunity Engine reads it; agents receive **role-scoped slices** of
it. It is the single source of business context — agents never learn their own private copy.

```
 Discovery Questionnaire ──answers──▶ Business Brain (facts, versioned, provenance)
        (JSON-defined,                      │            ▲
         adaptive)                          │            │ feedback (reviewed, never silent)
                                            ▼            │
                              AI Opportunity Engine ──▶ AI Transformation Plan (draft)
                                            │
                                            ▼
                 Agent context API ──role scope──▶ Core8 agents (system-prompt context block)
```

Customer journey mapping: Discovery → Pain Mapping → Business Mapping (questionnaire + Brain)
→ AI Opportunity Analysis (engine) → Solution Design (plan) → Agent Deployment (agent
assignments) → Learning (feedback) → Optimization (re-run discovery / regenerate).

## 1. Security, tenancy and context model

| Rule (issue #2) | Implementation |
|---|---|
| One governed Brain per tenant | `tenants` table; every Brain table has `tenant_id NOT NULL`. |
| Tenant isolation is mandatory | All data access goes through `BrainRepository(tenant_id)`; every SQL statement filters on `tenant_id`. Cross-tenant IDs return **404** (no existence leak). Covered by tests. |
| Don't expose all knowledge to every agent | `context.py` scopes = allowed **categories** × allowed **domains** × **max sensitivity**. `restricted` facts are never returned to agents. |
| High-risk actions need approval policies | Approval requirements are captured as facts and surfaced per opportunity (`risk_approval_level`). Tool execution still goes through the existing approval gate. |
| Corrections → feedback, no silent self-modification | `brain_feedback` rows are `pending` until a tenant **owner** accepts; acceptance writes a new fact version with `source_type=correction`. Agents cannot change policies or permissions. |
| Provenance + version history | Every fact has `fact_key`, `version`, `source_type`, `source_ref`, `created_by`, `created_at`; updates supersede, never overwrite. `/history` endpoint. |
| Retrieval ≠ authorization | The context block tells the agent it is reference data, not instructions or permissions; tool permissions remain `allowed_tools` + approval gate. |
| No secrets/PII in logs | Routes log IDs and counts only, never answer values. The questionnaire asks for **role titles**, not people's names or contact details. |
| My Goddess stays separate | No code shared or imported from `apps/my-goddess-orchestra`. |

### Access roles — explicit, per client (decided by Lev, 2026-10-02)
Every business is different, so **nobody has implicit access to a client's Brain** — including
Core8 staff. Access is always an explicit `tenant_members` row, recorded with `granted_by`.
- **Platform `admin`** (existing `users.role`) — Core8 staff. May create tenants (and becomes an
  owner of the tenant they create, to run onboarding) and see a **names-only client directory**
  (`/api/admin/tenants`). No access to any other tenant's data unless granted.
- **Tenant members** (`tenant_members.role`):
  - `owner` — everything + grant/revoke members (incl. Core8 staff), accept/reject feedback,
    set agent scopes. A tenant always keeps at least one owner.
  - `editor` — run discovery, answer, add facts, generate analysis/plan, submit feedback.
  - `viewer` — read only.
- Anyone else gets 404 for that tenant.

Cross-client learning ("main brain") is a separate, privacy-reviewed design — see issue CORE8-004.
It never gives staff or agents access to another client's raw data.

### Sensitivity
`public < internal < confidential < restricted`. Default per question (usually `internal`).
Each module asks `data_sensitivity` **first**; facts in that module take the stricter of the
question default and the module answer. If the answer changes later, existing active facts in
that module are re-labelled to the stricter level (only ever tightened).

## 2. Business Brain data model

| Table | Purpose | Key columns |
|---|---|---|
| `tenants` | Client company (Core8 customer) | id, name, created_by |
| `tenant_members` | User ↔ tenant membership (the only way to access a tenant) | tenant_id, user_id, role, granted_by |
| `brain_facts` | Versioned facts | tenant_id, fact_key, version, category, domain, value_json, sensitivity, status (`active`/`superseded`/`retracted`), source_type (`questionnaire`/`manual`/`correction`/`agent`/`import`), source_ref, confidence, created_by, supersedes_id |
| `discovery_assessments` | A discovery run | tenant_id, questionnaire_version, status, created_by, completed_at |
| `assessment_answers` | Raw answers | tenant_id, assessment_id, question_id, value_json, updated_by |
| `ai_opportunities` | Engine output (one row per opportunity per generation) | tenant_id, assessment_id, generation, module, phase, priority_score, payload_json |
| `transformation_plans` | Draft plans | tenant_id, assessment_id, version, status, content_json, markdown |
| `brain_feedback` | Corrections/flags | tenant_id, fact_id, kind, proposed_value_json, status, submitted_by(_type), resolved_by |
| `agent_assignments` | Recommended/approved agents per tenant + optional scope override | tenant_id, agent_role, status, context_scope_json |

**Fact categories:** `organization_profile`, `products_services`, `customer_personas`, `roles`,
`systems`, `processes`, `policies`, `tone_brand`, `knowledge_sources`, `kpis`, `goals`,
`metrics`, `pain_points`, `approval_requirements`.
**Domains:** `general` (executive intake) or a module id (`sales_crm`, `customer_service`, …).

Pain points, AI opportunities, agent assignments, permission/context scopes, approval
requirements and feedback from the issue's list are all represented above.

Writing a fact with the same `fact_key` and an identical value is a no-op; a different value
creates `version+1` and marks the previous one `superseded`.

## 3. Questionnaire schema and branching

Defined in `business_brain/questionnaire.json` — **data, not code**.

```jsonc
{
  "version": "1.0.0",
  "intake": { "id": "exec", "questions": [ /* question */ ] },
  "module_template": [ /* standard questions applied to every module */ ],
  "modules": [
    { "id": "sales_crm", "title": "...",
      "activation": { "any": [ {"question": "exec.focus_areas", "op": "includes", "value": "sales_crm"},
                               {"question": "exec.monthly_leads", "op": "gt", "value": 0} ] },
      "capability": { "agent_role": "leads", "availability": "available", "capability": "...",
                      "base_complexity": "medium", "risk": "medium", "default_kpi": "..." },
      "pain_keywords": ["lead", "sales", ...],
      "extra_questions": [ ... ] }
  ]
}
```

Question: `id`, `text`, `type` (`text` | `long_text` | `number` | `boolean` | `single_choice` |
`multi_choice` | `list`), `options`, `required`, `max_items`, `sensitivity`,
`maps_to: {category, key?}`. Module questions are generated from `module_template` with ids
`<module>.<field>` plus the module's `extra_questions`.

**Languages (decided by Lev, 2026-10-02): English, Hebrew, Russian.** Every question text,
section/module title and option label is stored as `{"en", "he", "ru"}`; loading fails if any
translation is missing (tested). Option values are stable codes (`sales_crm`, `high`, …), so
answers, branching rules and analysis are language-independent. Each assessment has a `locale`
(`POST …/assessments {"locale": "he"}`); `?lang=` overrides per request. Hebrew is served with
`direction: "rtl"`. Brain facts store the English canonical question text plus the client's
answer exactly as written, so agents get one consistent vocabulary. Adding a language = adding a
key to every text in the JSON.

**Activation operators:** `includes`, `includes_any`, `gt`, `equals`, `count_gte`, `answered`.
**Next question:** walk intake, then active modules in definition order; return the first
unanswered **required** question (optional ones are returned after all required ones, so a
client can stop early). Progress = answered required / total required across active modules.

v1 modules (all 12 from the issue): Sales & CRM, Customer Service, Office/Admin, Email &
Calendar, Marketing/Social, Operations, Finance (workflow only — no autonomous financial
transactions), HR, Management/BI, Knowledge/Documents, Integrations & IT,
Security/Compliance. Sales/CRM, Customer Service and Office/Admin have extra
module-specific questions and are covered end-to-end by tests.

## 4. Opportunity scoring

Deterministic and explainable (no LLM, no invented numbers). Input is the tenant's **current
Brain** (active questionnaire facts, including accepted corrections) — one Brain per tenant, so a
later assessment refines the same facts. For each **active module with answers**, each listed bottleneck becomes an opportunity. Executive top pains are mapped to a
module by keyword; unmapped pains become explicit **open questions**.

Per opportunity:

| Field | Source |
|---|---|
| pain statement | bottleneck / executive pain text |
| current process | `<module>.current_workflow` |
| frequency/volume | `<module>.monthly_volume`, else matching executive monthly volume, else `null` + assumption |
| manual effort | `<module>.hours_per_week` or `null` + open question |
| business impact | `<module>.business_impact` |
| automation suitability | `high`/`medium`/`low`/`unknown` from volume, hours/week, error rate |
| recommended agent/capability | module `capability` (marks `planned` agents that don't exist yet) |
| required integrations | systems used in the module (+ CRM system); empty → open question |
| implementation complexity | base complexity, +1 step if >2 integrations, +1 if confidential/restricted data |
| risk/approval level | max(capability risk, data sensitivity); "human approval required" if approvals are listed |
| KPI | client's answer, else the capability default **marked as a suggestion** |
| phase | `Now` / `Next` / `Later` |
| rationale | every score contribution as a sentence |
| assumptions / open questions | every missing input |

Suitability: volume ≥200/month +2, ≥30 +1; hours/week ≥15 +2, ≥4 +1; error rate ≥5% +1 →
high (≥3) / medium (≥1) / low; `unknown` when neither volume nor hours is known.

Priority score (0–100, clamped): 50 base; impact critical +25 / high +15 / medium +5 / low −5;
suitability high +15 / medium +5 / low −10; complexity high −15 / medium −5; risk high −10;
planned (not yet built) agent −5. Phase: **Now** if score ≥ 70, complexity ≠ high and the agent
exists; **Next** if score ≥ 45; else **Later**. **No ROI or savings figures are computed.**

## 5. AI Transformation Plan (draft)

Generated from the Brain + latest opportunities. Sections: Executive summary, Business pain
map, Current-state workflow map, Recommended AI workforce, Integrations required,
Implementation phases, KPIs / success criteria, Risks & approval controls, Information gaps /
assumptions. Stored as JSON and Markdown, versioned per assessment, status `draft`.
**No pricing** — that is the CORE8-002 commercial layer, which will consume this plan through
`GET .../plans/{id}`.

## 6. API (all JWT-protected)

| Method | Path | Min role |
|---|---|---|
| GET | `/api/discovery/questionnaire` | any user |
| POST | `/api/tenants` | platform admin (creator becomes owner) |
| GET | `/api/tenants` | any (only tenants you are a member of) |
| GET | `/api/admin/tenants` | platform admin (names + member counts only) |
| GET | `/api/tenants/{tid}` | viewer |
| GET / POST | `/api/tenants/{tid}/members` | owner (grant or change role; `granted_by` recorded) |
| DELETE | `/api/tenants/{tid}/members/{user_id}` | owner (last owner protected) |
| POST | `/api/tenants/{tid}/assessments` | editor |
| GET | `/api/tenants/{tid}/assessments/{aid}` | viewer — answers, active modules, progress, next question |
| PUT | `/api/tenants/{tid}/assessments/{aid}/answers` | editor — `{answers: {qid: value}}`, validated |
| GET | `/api/tenants/{tid}/assessments/{aid}/next` | viewer |
| POST | `/api/tenants/{tid}/assessments/{aid}/complete` | editor (requires all required answered) |
| POST/GET | `/api/tenants/{tid}/assessments/{aid}/opportunities` | editor / viewer |
| POST | `/api/tenants/{tid}/assessments/{aid}/plan` | editor |
| GET | `/api/tenants/{tid}/plans/{pid}` | viewer |
| GET | `/api/tenants/{tid}/brain/facts` | viewer (`?category=&domain=`) |
| POST | `/api/tenants/{tid}/brain/facts` | editor (manual fact) |
| GET | `/api/tenants/{tid}/brain/facts/{fid}/history` | viewer |
| POST | `/api/tenants/{tid}/brain/feedback` | editor |
| POST | `/api/tenants/{tid}/brain/feedback/{fbid}/resolve` | owner |
| GET | `/api/tenants/{tid}/brain/context?agent_role=` | viewer |
| PUT | `/api/tenants/{tid}/agents/{agent_role}/scope` | owner |

**Chat integration:** `WS /ws/{agent_id}?token=<jwt>&tenant_id=<tid>` — when `tenant_id` is given,
the JWT user must be a member (legacy bearer tokens are rejected for tenant chats) and the
agent receives its scoped Brain context as an extra system block. Without `tenant_id`,
behaviour is unchanged.

## 7. Known limits / follow-ups

- Existing tables (`leads`, `events`, `conversations`, …) are **not** tenant-scoped yet; tenant
  chats tag nothing new in those tables. Making the legacy agents' data tenant-scoped is a
  separate migration.
- SQLite remains the store (consistent with the platform). Postgres/Supabase migration is
  TECH_DEBT C5.
- No UI in this issue (API only, as allowed).
- No LLM summarisation of the plan yet; narrative text is templated from facts.
- The **Transformation Plan is generated in English** only; localising the plan output to
  he/ru is a follow-up. Free-text answers are kept in the language the client wrote them.
- Hebrew and Russian questionnaire texts were written by Claude Code and should be checked by a
  native speaker before client use.
