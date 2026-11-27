# Lead intake idempotency — implementation design (not deployed)

## Goal
Prevent duplicate lead creation under simultaneous requests, retries and network timeouts. The existing `dedup-preview.cjs` is only a pure in-memory demonstration and **cannot** prevent concurrency races.

## Transaction and API contract

1. Authenticate the caller on the server. Resolve `tenant_id` from trusted identity and authorization context; never accept tenant authority from the request body.
2. Validate request size, consent, source signature and canonical envelope. Enforce per-tenant rate limits.
3. Compute a stable SHA-256 digest over a versioned canonical representation of the original accepted request. Define normalization (field order, whitespace, encoding) explicitly and include the canonicalization version. Avoid placing personal information in database keys, logs or metrics.
4. Begin a PostgreSQL transaction. Insert an idempotency claim keyed by `(tenant_id, source_system, source_submission_id)` with `ON CONFLICT DO NOTHING RETURNING`. The unique index serializes conflicting concurrent inserts.
5. **If inserted:** create the lead and its append-only event in the **same transaction**, then commit. If any step fails, roll back both claim and lead.
6. **If conflict:** read the existing row after the conflict resolves. If the stored digest matches, return the original lead identifier with an explicit replay result. If the digest differs, return HTTP 409 and do not overwrite the original.
7. Ensure retry handling for transient database failures; do not retry unsafe external side effects inside the transaction. Outbound messaging should use a separate outbox worker with its own deduplication and approval checks.
8. Restrict DB privileges, add tenant isolation/RLS where appropriate, audit access, and define retention/erasure policies with legal review.

## Required concurrency verification before integration

- Two parallel requests with identical tenant/source/submission and identical payload produce **one** lead.
- Two parallel requests with identical key but different payload produce **one** lead and one conflict.
- Same submission ID across two tenants produces independent leads.
- Same submission ID across different sources produces independent leads.
- Crash after claim but before lead insert rolls back everything; retry succeeds.
- Crash after commit but before HTTP response returns the same lead on retry.
- No cross-tenant read of existing lead IDs or payload hashes.
- No actual emails, bookings, social posts or payments are sent by this endpoint.

## Status

`postgres-idempotency.proposal.sql` is a design artifact in a draft PR, **not** a migration executed on a database. The exact table shape and transaction code must be reconciled with the actual application schema, authorization model and operational policies before implementation.
