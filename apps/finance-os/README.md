# Core8 Finance OS — sandbox-only v0.3 review candidate

Status: **NOT production-ready**. No charges, live invoices, tax filings, or payroll changes.

The initial standalone prototype is available as the chat artifact `core8-finance-os-v0.3.zip`. This repository branch contains the first auditable safety/policy slice and engineering acceptance checklist; it is **not** a deployed payment system.

## Security/architecture
- Webhook payload signature validation is mandatory; never fulfill orders from the redirect success page.
- Fail closed on `livemode != false`. Sandbox only.
- Capture only non-PII event metadata: `event_id`, `event_type`, `source_object_id`, `event_created`, merchant mapping.
- Store events with unique event ID and process idempotently; no accounting entries or revenue recognition derived simply from event receipt.
- Authenticate/authorize each financial API with tenant boundary checks before exposing it.
- Use separate Stripe sandbox secrets stored in secret vault; never commit keys or billing/customer data.
- Implement a durable worker, retry/dead-letter handling, audit log and full reconciliation before payments release.
- No automatic tax until legal entity, head office, product tax codes, required registrations and compliant invoicing are verified.
- Israel-issued fiscal documents, Israel Invoices allocations, payroll calculations, tax submissions require approved integrations and professional review.

## Integration with LEV OS
Existing platform is in `apps/core8-platform` (FastAPI + Next.js). Keep finance module separate until existing tenant isolation and security gates close in `docs/LAUNCH_READINESS.md`.

## Verification
In the isolated development artifact, 5 pure event policy tests passed locally on 2026-11-22; 5 integration-related tests were skipped because Stripe/psycopg dependencies were absent. GitHub CI must validate these and check database concurrency, webhook signatures, duplicate deliveries and forbidden production behavior.

## Release gates
1. Complete isolated sandbox application with migration and tested webhook events.
2. Approve RBAC/tenant mapping and explicit human confirmation flows.
3. Validate fiscal, tax, and payroll provider by jurisdiction.
4. Review code and CI in PR; do not merge/deploy/live-charge without explicit Lev approval.

Tracking: #63.
