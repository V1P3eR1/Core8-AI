# Finance OS release gates — human approval mandatory

> **TBD policy (2026-11-22):** Every missing owner decision, private detail, unsupported fact, unverified vendor feature and incomplete engineering gate is labeled **TBD**. Canonical decision register: [OWNER_INPUTS.md](OWNER_INPUTS.md). No arbitrary substitute values, inferred business registrations, fake approvals or production claims.

**Current scope (2026-11-22):** isolated Stripe sandbox event inbox and operational activity metadata. No money movement. The draft balanced journal is an isolated prototype, not a finalized or integrated accounting ledger; no legal invoicing, wages, tax filings or customer-facing UI. The successful sandbox test is evidence for **this narrow scope only**.

## Proof required before launch
1. Merge no changes before manual code review; pass security and PostgreSQL integration CI.
2. Integrate with LEV OS authentication: OIDC identity, per-tenant RBAC, no shared bearer in browser, denied cross-tenant access.
3. Configure restricted Stripe sandbox credentials via secrets manager, then restricted live credentials only on explicit approval.
4. Implement and test Checkout Sessions, subscriptions, invoice lifecycles, Customer Portal and payment retries; consume signed webhooks for fulfillment.
5. Execute payment/refund/dispute reconciliation against Stripe reports and bank settlements, including different currencies and chargebacks.
6. Adopt approved Israel-compliant document provider; obtain legal entity, VAT registration, accounting method, document numbering, allocation-number requirements and foreign-sales rules from the CPA.
7. Use approved payroll solution and payroll professional for legal employer registrations, deductions, filings, worker privacy; do not infer employee wages.
8. Security: close blockers in `docs/LAUNCH_READINESS.md`, add audit logs, backups/restore tests, RTO/RPO, dependency scans, risk and permission gates.
9. Obtain explicit Lev approval for any live charges, live invoices, payroll, refunds, deployment, PR merges or recurring paid services.

## Current software guarantees
- Stripe signatures validated over raw bytes, with ±5m tolerance, before parsing event.
- `livemode: true` or unknown value always rejected.
- Deterministic event ID primary key prevents duplicate inbox messages.
- Financial overview returns 503 until identity and tenant policy are integrated.
- Worker records **operational events**, never financial ledger entries.
- Worker isolates individual row failures with PostgreSQL nested transactions, retries failed rows with exponential backoff (maximum 5 attempts), and marks exhausted rows `dead`; errors are not persisted as strings.
- Updated worker unit tests and real PostgreSQL fault-injection/concurrency tests passed in [Finance OS CI #32](https://github.com/V1P3eR1/Core8-AI/actions/runs/45037658905). Scope is limited to durable inbox and activity metadata, not end-to-end financial fulfillment.
- Latest [secret-scan #306](https://github.com/V1P3eR1/Core8-AI/actions/runs/45037658924) succeeded on commit `e28a604`. A real provider-originated Stripe delivery and external effects remain untested.

## Retry/dead-letter release gaps
1. **Verified in CI #23 and #32:** real PostgreSQL fault-injection covers savepoint rollback, continued processing, retry scheduling and the dead-letter transition.
2. Add a restricted operator-only dead-letter review and replay procedure; do not automatically replay potentially harmful financial events.
3. Add limited retry/dead-letter metrics with no customer identifiers in logs; verify external alerting and backup/restore.
4. **Verified in CI #32:** real PostgreSQL tests exercise `FOR UPDATE SKIP LOCKED` with a held row lock and two concurrent workers, proving one activity row per tested event. Measure throughput and transaction contention separately before production; this prototype makes **no** exactly-once guarantee for external side effects.

## Manual local sandbox test
1. Create a sandbox webhook signing secret through Stripe's CLI/dashboard (never use live keys).
2. From `apps/finance-os`, set `STRIPE_WEBHOOK_SECRET` outside Git and run `docker compose up --build`.
3. API binds only to `127.0.0.1:8008`; `GET /health` provides the sandbox-only flag.
4. Forward **sandbox** Stripe events to `http://localhost:8008/webhooks/stripe` and check the PostgreSQL inbox. No financial fulfillment is triggered.
5. Run worker only on the local sandbox database after verifying tests.

## Evidence vs completion
- CI success != Stripe Checkout success.
- An operational webhook event != revenue, tax receipt, deposit or journal entry.
- Human review of real tax and payroll workflows is mandatory.
