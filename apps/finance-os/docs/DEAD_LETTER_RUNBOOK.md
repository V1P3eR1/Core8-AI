# Finance OS — dead-letter triage runbook (sandbox only)

**Status:** DRAFT / NOT AN APPROVED OPERATING PROCEDURE. No production deployment, live payment action or automated replay is authorized.

**Scope:** `finance_stripe_event_inbox` and `finance_activity` hold operational metadata only. Neither table is a bank ledger, payable, tax receipt or evidence that a Stripe payment settled.

## 1. Safety boundaries

- Run only against an isolated, authorized **sandbox** PostgreSQL database. The local CLI/SQL examples are **read-only** and must use a dedicated role with `SELECT` privileges, network restrictions and a documented human operator.
- Never connect this prototype to live Stripe secrets or production databases; `APP_ENV` must be `sandbox`, `development` or `test` and `ENABLE_STRIPE_WRITES=false`.
- Do not log full Stripe payloads, personal emails, customer references or error strings. Use aggregate counts for shared incident reports; an authorized reviewer may inspect minimum necessary event IDs in a restricted audit environment.
- `dead` means the worker exhausted its retry budget (five attempts); it **does not** prove a refund, subscription, billing or financial settlement failed.
- No automatic replay is implemented. Replaying must not be attempted by changing `status` or `attempts` in a production database.

## 2. Read-only dashboard queries

Run these through an approved read-only database client. Do not paste database credentials into GitHub, Notion or chat.

```sql
-- Total operational events by status, without customer identifiers.
SELECT status, count(*) AS event_count
FROM finance_stripe_event_inbox
GROUP BY status ORDER BY status;
```

```sql
-- Aggregate due retries and dead letters.
SELECT
  count(*) FILTER (WHERE status='failed' AND next_attempt_at <= now()) AS due_retries,
  count(*) FILTER (WHERE status='failed' AND next_attempt_at > now()) AS scheduled_retries,
  count(*) FILTER (WHERE status='dead') AS dead_letters,
  count(*) FILTER (WHERE status='received') AS new_events
FROM finance_stripe_event_inbox;
```

```sql
-- Detect status/operational-log inconsistencies without exposing IDs.
SELECT
  count(*) FILTER (WHERE i.status='processed' AND a.stripe_event_id IS NULL) AS missing_activity,
  count(*) FILTER (WHERE i.status <> 'processed' AND a.stripe_event_id IS NOT NULL) AS unexpected_activity
FROM finance_stripe_event_inbox AS i
LEFT JOIN finance_activity AS a ON a.stripe_event_id=i.event_id;
```

If an inconsistency is nonzero, do not perform live fulfillment. Escalate to an operator with restricted logs and investigate transaction boundaries and source verification.

## 3. Escalation, evidence and disposition

1. Identify the incident in the private Notion task with an aggregate count, run ID and CI version. **Do not** export identifying event details to the public GitHub repo.
2. Confirm sandbox environment, affected tenant mapping and current webhook signing-secret rotation status without disclosing the secret.
3. Verify that the error is understood and its underlying cause corrected. Record the class of failure, not raw exception text.
4. Determine whether the Stripe event needs no action, requires a fresh provider API reconciliation, or is still unsafe to process. Payment state is authoritative only after a separate verified provider reconciliation.
5. Obtain explicit owner/operator approval and a reviewed replay plan that re-verifies account ownership, signature/source, idempotency and event freshness. No owner approval is implied by a task having `Decision=Approved` for sandbox development.
6. Preserve the original inbox record and immutable audit trail. **Replay tooling is TBD**; do not bypass the retry limit with ad-hoc database edits.
7. Validate in disposable PostgreSQL CI with concurrent workers and failure injection; review metrics and rollback plan before enabling any privileged path.

## 4. Remaining release gates (TBD)

- Authenticated operator console (OIDC + tenant-scoped RBAC + audit log), separate from the public webhook endpoint.
- Reviewed and tested replay semantics that cannot trigger duplicate external money movement, with manual two-person approval for privileged actions as determined by policy.
- Source-of-truth reconciliation against Stripe sandbox account with provider-originated webhook test and signature verification.
- Structured, privacy-safe telemetry, secret management, backed-up immutable audit trails and retention/deletion policy approved for the legal jurisdiction.
- CPA/legal sign-off for Israeli bookkeeping, fiscal documents and payroll before relevant modules are enabled.

**Evidence:** [Finance OS CI #33](https://github.com/V1P3eR1/Core8-AI/actions/runs/45037741867) and [secret scan #307](https://github.com/V1P3eR1/Core8-AI/actions/runs/45037741814) passed on commit `6e12623`. This evidence is for the sandbox inbox implementation and tests only.
