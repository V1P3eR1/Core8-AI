# Core8 Main Brain — design and privacy threat model (CORE8-004, issue #6)

_Status: **design for review — nothing here is implemented.** Owner decisions already made:
access is per client (2026-10-02); contributing to the Main Brain is **opt-in** per client._

## 1. Purpose

Each client has a private **Business Brain** (tenant-scoped, merged in #5 and #8). The **Main
Brain** lets Core8 improve from what it sees across clients — which pains occur where, which
agents get approved and work — **without any client's data reaching another client, Core8 staff,
or an agent**.

The Main Brain holds **patterns, never data**. If a row could only have come from one
identifiable client, it does not belong there.

## 2. What it produces

| Output | Example | Used by |
|---|---|---|
| Pain → solution patterns | In *healthcare services, 11–50 staff*, the pain keyword *lead follow-up* most often leads to an approved `leads` agent | Opportunity Engine, as a labelled extra signal |
| Benchmarks by segment | Hours/week on appointment handling: **range** 6–15 | Transformation Plan, shown as "Core8 benchmark" |
| Outcome learning | Share of recommended agents that were approved → deployed | Opportunity scoring weights |
| Questionnaire improvement | Questions most often skipped or corrected; pains that mapped to no module | Questionnaire maintainers |

Playbook/prompt improvements derived from corrections are **out of scope for v1**: corrections
are free text, and free text is never exported (§4).

## 3. Architecture

```
 Tenant Brains (tenant_id on every row)              Main Brain (no tenant_id anywhere)
 ┌──────────────────────────────┐   one-way export    ┌─────────────────────────────────┐
 │ brain_facts, ai_opportunities│ ──────────────────▶ │ main_brain_runs                 │
 │ agent_assignments,           │  allow-listed       │ main_brain_patterns (published) │
 │ assessment_answers           │  structured fields  │ main_brain_benchmarks           │
 └──────────────────────────────┘  + k-anonymity gate └───────────────┬─────────────────┘
          ▲  never reads Main Brain tables directly                   │ versioned, read-only
          └────────── PatternLibrary interface ◀──────────────────────┘
```

- **Separate tables** prefixed `main_brain_`, with **no `tenant_id` column and no foreign key**
  to any tenant table. A test asserts this on the schema.
- **One-way.** The export job is the only code that reads tenant tables for this purpose and
  the only code that writes Main Brain tables. Nothing writes back into a tenant Brain.
- **PatternLibrary** is the only read path: `get_pattern(segment, module)`,
  `get_benchmark(segment, metric)`. It returns published rows of the latest run. Tenant-facing
  code and agents never query Main Brain tables.
- The export job runs **without a tenant context** as a system job (like the scheduler's
  cross-tenant read), is not a registered tool, and cannot be called by an agent.

## 4. What may be exported (allow-list)

Only fields on this list leave a tenant. Anything not listed is not exported — the job selects
named fields; it never copies `value_json` or `payload_json` wholesale.

| Field | Source | Form in Main Brain |
|---|---|---|
| Industry | `exec.industry` (**free text today**) | Mapped to a fixed category list (~20). Unmapped → `other`. Raw text never stored |
| Size | `exec.employee_count` | Band: 1–10, 11–50, 51–200, 201+ |
| Focus areas, active modules | option codes | Codes as-is (controlled vocabulary) |
| Opportunity | `module`, `phase`, impact rating, complexity, risk, recommended agent role | Codes as-is |
| Numeric answers | monthly volume, hours/week, error rate | Bucketed; published only as a range (§5) |
| Agent outcome | `agent_assignments.status` | recommended / approved / deployed / disabled |
| Questionnaire quality | question id + answered / skipped / later corrected (boolean) | Counts per question |

**Never exported:** company or person names, contact details, any free text (workflows, pain
statements, notes, corrections, messages, documents, lead data), `source_ref`, user ids, tenant
ids, timestamps finer than the month, and anything from a fact with sensitivity `confidential`
or `restricted` or from a sensitive category (health, payment cards, HR, legal, children).

`exec.industry` being free text is a real gap: v1 needs a controlled industry option list in the
questionnaire (new question version), with the free-text answer kept only in the tenant Brain.

## 5. Privacy rules

1. **Consent (opt-in).** `tenants.contribute_to_main_brain` — default **false**. Only the
   tenant **owner** can turn it on; the change is recorded (who, when, consent-text version),
   using the same versioned-text pattern as lead-form consent. The Core8 internal tenant is
   excluded unless Lev opts it in.
2. **k-anonymity.** A segment row is published only if it aggregates **≥ 5 distinct consenting
   tenants** (`K_MIN = 5`, configurable upward only). Below that it is not written at all — not
   stored hidden.
3. **Dominance rule.** If one tenant contributes more than 50 % of the underlying records of a
   cell, the cell is suppressed.
4. **Ranges, not values.** Numbers are bucketed before aggregation and published as an
   inter-quartile range, never min/max/mean of exact values.
5. **No small-difference leaks.** Each run is a full recomputation from current consenting
   tenants. The previous run's patterns are replaced, not diffed, and run history keeps only
   counts-above-k and segment definitions. A segment that drops below k disappears in the next run.
6. **Withdrawal.** Turning consent off excludes the tenant from the next run. Because every run
   recomputes from scratch, its contribution is gone from published patterns after that run.
   Deleting a tenant has the same effect.
7. **Segment coarsening.** If (industry × size) is below k, try industry alone, then size alone;
   never publish the finer cell.

## 6. Threat model

| # | Threat | Mitigation |
|---|---|---|
| T1 | A client sees another client's data through a "benchmark" | Allow-list (§4), k ≥ 5, dominance rule, ranges only |
| T2 | Re-identification of a client in a tiny segment (e.g. the only 200-person dental chain) | k-anonymity + coarsening; unmapped industries pooled as `other` |
| T3 | Differencing: compare two runs to isolate a tenant that joined or left | Full recomputation; segments near k (5–6 tenants) are published with a one-run delay and only if still ≥ k; no per-run tenant counts exposed below a rounded band |
| T4 | Free text carrying names or secrets leaks via export | Free text is never selected; a test builds a tenant with marker strings in every free-text field and asserts no marker appears in any Main Brain table |
| T5 | Core8 staff trace a pattern to a client | No tenant ids in Main Brain; run log stores counts and segment definitions only |
| T6 | An agent is prompted to dump Main Brain contents | Agents have no tool that reads it; PatternLibrary output reaches prompts only as a small labelled block for the tenant's own segment |
| T7 | Poisoning: one tenant feeds fake answers to skew patterns | Dominance rule; each tenant counts once per cell; patterns are advisory and labelled |
| T8 | Sensitive-category data exported by mistake | Facts flagged `confidential`/`restricted` and sensitive categories are filtered before field selection; covered by test |
| T9 | Consent turned on by someone without authority | Owner role required, recorded with user and consent-text version; default off |
| T10 | Export job bug writes tenant ids | Schema has no column to hold them; schema test; code review gate on any `main_brain_` DDL change |

Residual risk: with few clients, most segments will be below k and the Main Brain will be nearly
empty. That is the intended behaviour — it starts being useful only at real scale. Differential
privacy noise is a v2 option if benchmarks are ever shown outside Core8's own clients.

## 7. Use in the product

- **Opportunity Engine:** may add a signal *"similar businesses usually approve this"* with a
  small, capped score adjustment. The client's own answers always outweigh it, and the rationale
  names it as a Core8 benchmark.
- **Transformation Plan:** benchmark ranges appear in a separate, labelled block. They are never
  merged into the client's own figures (keeps the #2 rule: no fabricated metrics).
- **Core8 staff view:** aggregate patterns only, admin role, read-only.

## 8. Implementation plan (after this design is approved)

1. Questionnaire v1.2: controlled industry list (EN/HE/RU), keep free text locally.
2. Consent: tenant setting + versioned consent text + owner-only endpoint + audit row.
3. `main_brain_*` schema + schema test (no `tenant_id`, no FKs).
4. Export job with allow-list, k-anonymity, dominance and coarsening; marker-string leak test;
   below-k test; withdrawal test.
5. PatternLibrary (read-only) + labelled use in Opportunity Engine and Plan.
6. Admin read-only view.

Each step is its own PR. No step exports anything until step 2 (consent) is merged.

## 9. Decisions

| Decision | Status |
|---|---|
| Consent default | ✅ Opt-in (Lev) |
| Client agreements mention aggregated, anonymised learning | ⏳ **Needs Lev + legal wording** — required before the first tenant can opt in |
| `K_MIN = 5`, dominance 50 % | Proposed — reviewer may raise |
| Internal tenant contributes | Proposed: no, unless Lev opts in |
