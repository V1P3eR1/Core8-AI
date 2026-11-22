# Core8 Finance OS — owner decisions and TBD register (2026-11-22)

## Status conventions
- **VERIFIED** — backed by connected account, GitHub CI or official published source.
- **IN PROGRESS** — engineering deliverable exists but end-to-end functionality is not finished.
- **TBD** — no sufficiently verified source or explicit owner decision exists. Do not fill with guesses.
- **BLOCKED — TBD** — implementation cannot legally/safely proceed until the missing decision is confirmed.
- **N/A** — formally ruled out by owner, never an assumption.

**Owner data rule:** mark every unresolved owner decision with the literal token `TBD`. Mark any other unknown (vendor pricing, provider availability, compliance classification, operational value) `TBD` too until verified. Never infer a private fact from public internet research. No customer/payment/employee personal data in GitHub, Notion or public project trackers. Secrets via dedicated encrypted secret manager only.

## Verified facts (NOT TBD)
| Item | State | Evidence |
|---|---|---|
| Stripe connection for Core8-AI | VERIFIED | Connected live-mode account, read-only review 2026-11-22 |
| Existing Stripe live catalog | VERIFIED | No products, prices, customers, invoices or subscriptions returned in initial read |
| Stripe Tax | VERIFIED — pending | Missing `head_office` in account Tax settings; never assume Tax collection is operational |
| Finance OS sandbox CI | VERIFIED | GitHub Finance OS run #15 succeeded, secret scan #261 succeeded |
| Israel Invoices 2026 allocation threshold | VERIFIED | Official Tax Authority: relevant tax invoices over NIS 5,000 before VAT from 2026-06-01: https://www.gov.il/he/pages/pa240525-1 and https://www.gov.il/he/service/request-assignment-number-for-tax-invoice |

## TBD — Lev or accountant must decide
| Field | Current | Owner / source | Why it matters | Safe handling |
|---|---|---|---|---|
| Legal entity collecting Core8-AI payments, registration country and business form | **TBD** | Lev / registration certificate | Determines issuer, taxation, contracts, Stripe settings | Share category/country only in issue, sensitive details through vendor onboarding |
| Registered head-office business address for Stripe Tax | **TBD** | Lev / entity records | Required for Stripe Tax activation | Enter privately in Stripe dashboard; not GitHub |
| VAT status and registrations | **TBD** | Accountant / tax records | Correct product tax behavior and compliance | Professional validation before enabling |
| Official invoice/receipt issuer for Israel | **TBD** | Lev + accountant, shortlisted providers | Legal documents, numbering and allocation integration | Evaluate features/contracts; no subscription without approval |
| Accounting system of record / chart of accounts | **TBD** | Accountant | Prevent double books and wrong ledger postings | Keep draft-only |
| Business pricing and approved products per currency | **TBD** | Lev | Prevent unapproved prices and charges | No live Product/Price created |
| Stripe currency/settlement and payout arrangements for legal entity | **TBD** | Stripe account settings + Lev | Reconciliation and FX differences | Read-only investigation first |
| Initial employee vs contractor payroll scope | **TBD** | Lev | Determines whether local payroll provider is necessary | No salaries or payroll filings |
| Payroll vendor and licensed professional reviewer | **TBD** | Lev + accountant/payroll professional | Statutory salary, benefits and taxes | No payroll processing |
| Approved cloud host and budget | **TBD** | Lev | Secure infrastructure and cost consent | No paid deployment |
| Approver(s) for charges, refunds, tax, payroll and production release | **TBD** | Lev | Four-eyes controls and risk policy | Deny side effects by default |
| US/EU sales tax nexus, B2B tax treatment and cross-border invoicing | **TBD** | Accountant / jurisdictions | Multi-country VAT/sales tax | Do not guess exemption or rates |
| Real Stripe sandbox credentials and external webhook test endpoint | **TBD** | Stripe Sandbox owner | Needed for provider-originated E2E verification | Store in secrets vault, not GitHub |
| Production deployment date | **TBD** | Lev + security reviewer | Depends on all release gates | No production launch claim |

## Engineering work (does not require Lev to fill TBDs yet)
| Deliverable | State |
|---|---|
| Signed webhook sandbox ingestion + PostgreSQL inbox | IN PROGRESS — implemented and CI tested with synthetic signed events |
| Event deduplication and worker activity processing | IN PROGRESS — CI-tested in disposable PostgreSQL; not an accounting ledger |
| Draft-only double-entry journal validator | IN PROGRESS — validation only; does not post entries |
| Tenant-bound draft Checkout intent gate | IN PROGRESS — validation only; no Stripe Checkout API calls |
| Stripe-hosted real sandbox Checkout/Billing/Portal | **TBD — not yet implemented** |
| OIDC, approved tenant authorization and roles | **TBD — not yet integrated** |
| Financial reconciliation, refunds, disputes and bank settlements | **TBD — not yet implemented** |
| Legal invoice and payroll automation | **BLOCKED — TBD** |
| Customer-ready finance dashboard | **TBD — not yet implemented** |

## User action protocol
Do not ask Lev repeatedly for information already shared. For any missing value, keep `TBD` in the backlog and continue safe engineering. When decisions truly block further progress, provide a concise numbered owner checklist referencing this file, separating free/config-only tasks from paid/regulated changes.

**Do not request keys, bank details, tax IDs, salaries or unredacted documents in public GitHub comments.**

Full completion requires: provider-originated test payments, verified accounting and tax documents, tenant authorization, reconciliation, operational reliability and approved production release. Unit CI success is not completion.
