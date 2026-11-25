# Financial agents — scoped roles, not autonomous regulated practitioners

Each agent requires a distinct identity, tool allowlist, cost controls, sensitive-data redaction, tenant scope, audit traces, and approval queue. Do not give a model unrestricted Stripe keys.

| Role | Allowed once access is verified | Explicitly prohibited without human approval |
|---|---|---|
| CFO | Cashflow forecasts from approved ledger, budget simulations | Change bank details, transfer money, investment trades |
| Collections | Draft dunning messages from unpaid invoices | Send notices, waive fees, change mandates |
| Billing | Draft pricing proposals, detect upcoming renewals | Charge cards, refund, cancel subscription |
| Bookkeeper | Suggest GL categories, duplicate detection, reconcile reports | Post final journals, amend official fiscal documents |
| Tax | Gather deductible expense records, prepare review packets | Apply VAT status blindly, file tax returns |
| Payroll | Draft pay run checks and variances | Pay wages, transmit employee PII or file payroll |
| Auditor | Alert on gaps, fraud indicators, anomalous refunds | Freeze accounts without predefined policy and review |

Privacy: Ledger facts stay in Postgres; Obsidian may store strategy, Notion work items, Drive encrypted compliance backups, and GitHub versioned **code and sanitized documentation only**. No PII, salaries, tax IDs, API secrets, or full webhook payloads in GitHub/Notion/Obsidian.
