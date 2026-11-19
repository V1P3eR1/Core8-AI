# Commercial Engine — design (CORE8-002, issue #3)

_Status: **design for review — nothing here is implemented.** No prices in this document are
decided; every amount is a placeholder until Lev sets the first price book._

## 1. Purpose

Turn an approved **AI Transformation Plan** into a **draft commercial proposal** (setup fee,
recurring fee, usage limits, add-ons), and track recurring revenue (MRR/ARR) once customers
sign. ₪10K MRR is a first checkpoint, not a ceiling: pricing must be rules-driven and versioned
so it scales without rewriting.

Out of scope for v1: payment processing, invoicing, tax. Interfaces are left for them (§9).

## 2. Principles (from the issue)

1. **Composable pricing, simple presentation.** Internally: SKUs + rules. Customer-facing: the
   result may be labelled Start / Growth / Pro / Custom.
2. **Nothing unlimited by default.** Every usage meter has an included quantity and an overage
   rule, or a hard cap.
3. **Margin is visible.** Every line item carries an estimated cost; the proposal shows gross
   margin internally and never to the customer.
4. **Discounts are explicit.** A discount is its own line with a reason and an approver.
5. **No fabricated ROI.** Proposals show customer-supplied numbers and labelled assumptions only.
6. **Prices are versioned.** A customer stays on the price-book version they signed.

## 3. Inputs from the Business Brain (dependency on CORE8-001)

The engine reads only through one function, so the Brain's storage can change freely:

```python
commercial_inputs(tenant_id, plan_id) -> CommercialInputs   # plan must be status='approved'
```

| Input | Brain source | Used for |
|---|---|---|
| Recommended agents | `ai_opportunities.payload.recommended_agent`, phase Now/Next/Later | AgentSKU lines; phase → proposal phase |
| Complexity, risk, approvals | opportunity payload | Setup effort multiplier; service tier floor |
| Systems to integrate | `<module>.systems_used`, `crm_system` | IntegrationSKU lines |
| Monthly volume | `<module>.monthly_volume` | Included usage and overage estimate |
| Company size | `exec.employee_count` | Onboarding/training effort band |
| Sensitive data | `data_sensitivity` | Compliance add-on; approval level |

Missing inputs are **not guessed**: the line is priced at the rule's stated default and listed
under "Assumptions" in the proposal, or the proposal is blocked with the open questions (same
pattern as the Opportunity Engine).

Gaps in CORE8-001 this design depends on: (a) a stable `capability`/agent-role code per
opportunity (exists); (b) plan status `approved` (exists); (c) a controlled list of integration
systems — today free text, so v1 maps known names and prices unknown systems as "custom
integration — to be scoped".

## 4. Data model

All commercial tables are **tenant-scoped** (`tenant_id`, fail-closed like the rest) except the
catalogue and price book, which are Core8-global and admin-only.

| Entity | Scope | Key fields |
|---|---|---|
| `ProductCapability` | global | code, name |
| `AgentSKU` | global | code, capability, base complexity |
| `IntegrationSKU` | global | code, system name, effort class (standard / complex / custom) |
| `ServiceTier` | global | code (start/growth/pro/custom), SLA, support hours, optimisation cadence |
| `UsageMeter` | global | code (ai_tokens, whatsapp_msgs, voice_minutes, ig_posts), unit, unit cost |
| `PriceBookVersion` | global | version, status (draft/active/retired), currency, effective_from, created_by |
| `PricingRule` | per price book | target SKU/meter, kind (setup / recurring / included_usage / overage), amount or formula params, cost estimate |
| `DiscountRule` | per price book | code, max %, who may approve |
| `CustomerProposal` | tenant | plan_id, price_book_version, status (draft/sent/accepted/rejected/expired), term (monthly/annual), totals, margin |
| `ProposalLineItem` | tenant | proposal, kind, SKU, qty, unit price, cost, phase, rule id that produced it |
| `ContractSubscription` | tenant | proposal, **pinned price_book_version**, start, term, status |
| `SubscriptionAddOn` | tenant | subscription, SKU, from/to dates |
| `UsageRecord` | tenant | subscription, meter, period, quantity |
| `MrrMovement` | tenant | date, kind (new/expansion/contraction/churn/reactivation), amount, cause |

`PriceBookVersion` rows are immutable once `active` (database trigger, as for consent texts). A
price change is a new version. Existing subscriptions keep pointing at theirs.

## 5. Pricing calculation

```
setup fee      = Σ agent setup × complexity multiplier
               + Σ integration setup (by effort class)
               + onboarding/training (by size band)
recurring fee  = service tier base
               + Σ agent recurring
               + Σ integration maintenance
               + add-ons
usage          = per meter: included quantity (in recurring) + overage price per unit above it,
                 with a monthly cap unless explicitly raised
discounts      = explicit lines; annual-term discount is a DiscountRule, not a hidden price
margin         = (price − Σ estimated cost) / price, per line and total
```

- Deterministic: same inputs + same price book version → same proposal. No model call sets a
  price.
- Money as integer minor units (agorot) with a currency code; no floats.
- A proposal below the price book's minimum margin needs admin approval and is flagged.
- Tier presentation: the customer label (Start/Growth/Pro/Custom) is derived from the result
  (number of agents, SLA), not the other way round.

## 6. Proposal output

Generated as structured JSON plus Markdown (like the Transformation Plan), status `draft`:
pains and objectives (from the plan) · proposed AI workforce · implementation scope ·
integrations · setup fee breakdown · monthly fee breakdown · included usage and limits ·
estimated variable usage (only where volume is known) · phases and timeline · customer
responsibilities · Core8 responsibilities · KPIs · assumptions and exclusions · optional add-ons.

A draft is never sent automatically. Sending is a human action.

## 7. MRR / ARR model

MRR is derived from `ContractSubscription` + `SubscriptionAddOn`, recurring lines only (setup and
usage excluded; annual contracts counted at 1/12 per month).

| Metric | Definition |
|---|---|
| MRR / ARR | Σ active recurring per month; ARR = MRR × 12 |
| New / Expansion / Contraction / Churned MRR | From `MrrMovement`, written when a subscription starts, gains/loses add-ons or tier, or ends |
| ARPA | MRR ÷ active customers |
| Setup revenue | Σ accepted setup fees in period |
| Recurring gross margin | (MRR − recurring cost estimates − actual usage cost) ÷ MRR |
| Variable AI/API cost | Σ `UsageRecord` × meter unit cost |
| Pipeline | Σ draft/sent proposals; weighted value only with explicit, stored stage probabilities |
| CAC, LTV | **Not computed** until real sales and retention data exists; shown as "insufficient data" |

Checkpoints (first customer, ₪10K, ₪25K, ₪50K, ₪100K, ₪250K+ MRR) are displayed as reached /
not reached. No dates or forecasts are attached.

## 8. API (v1)

| Endpoint | Role |
|---|---|
| `GET/POST /api/admin/price-books`, `POST …/{v}/activate` | platform admin |
| `POST /api/tenants/{id}/proposals` (from an approved plan) · `GET …` | tenant owner / Core8 admin |
| `POST /api/tenants/{id}/proposals/{pid}/accept` → creates subscription | tenant owner |
| `POST /api/tenants/{id}/subscriptions/{sid}/add-ons` · `…/cancel` | Core8 admin |
| `GET /api/admin/revenue/summary` | platform admin |

Agents get **no** tools on commercial data in v1.

## 9. Future billing interface

`BillingProvider` protocol (`create_customer`, `create_subscription`, `report_usage`,
`cancel`), with a no-op implementation in v1. Subscriptions store an optional external id.

## 10. Tests (acceptance criteria → tests)

- Pricing: fixed inputs + fixed price book → exact totals; complexity and integration effects.
- Versioning: new price book does not change an existing subscription's price or MRR.
- No unlimited usage: every meter line has an included quantity and overage or cap.
- Discounts: only as explicit lines, within the rule's max, with approver.
- MRR movements: new, expansion, contraction, churn, annual = 1/12.
- Proposal blocked or assumption-listed when inputs are missing; never guessed.
- Tenant isolation on proposals and subscriptions; admin-only price books.

## 11. Implementation plan (after review)

1. Schema + catalogue + price book (immutable versions) + admin API.
2. Pricing calculation + proposal draft from an approved plan.
3. Subscriptions, add-ons, MRR movements, revenue summary.
4. Usage records and margin with actual usage.

## 12. Decisions needed from Lev (commercial model)

| # | Decision | Note |
|---|---|---|
| 1 | **First price book:** setup and monthly prices per agent, integration class and tier | Nothing can be quoted without it. I can draft a starting table for him to edit |
| 2 | Currency: ILS only, or ILS + USD | Affects price book shape |
| 3 | Minimum gross margin that triggers approval | Proposal: 60 % |
| 4 | Annual-contract discount | Proposal: explicit rule, e.g. 2 months free |
| 5 | Usage: pass-through at cost + fee, or bundled with caps | Affects every meter |
| 6 | Paid discovery/audit as a product line | Issue lists it as revenue layer 1 |
