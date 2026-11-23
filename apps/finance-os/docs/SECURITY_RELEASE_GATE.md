# Finance OS — security acceptance and production-release gate

**Status (2026-11-23): BLOCKED — review-only Sandbox.** This is an engineering
acceptance ledger, **not** approval to expose the Finance API or deploy payment
handling. Keep draft PR #64 unmerged until independent security review.

## Implemented and evidenced in isolated CI

| Control | Evidence | Scope |
|---|---|---|
| Tenant policy, deny-by-default public Finance API | `tenant_access.py`, HTTP tests | Policy only; no trusted public principal |
| Signed JWKS state and monotonic rotation candidates | `jwks_state_candidate.py`, `jwks_store_candidate.py` | Offline signed state and disposable PostgreSQL |
| Independent generation-floor CAS contract | `external_floor_candidate.py` | Abstract floor, fake test implementation |
| Dual-operator key rotation approval contract | `key_approval_candidate.py` | Unwired identity and approval policy |
| PostgreSQL consume-once approval + same-transaction audit | `approval_ledger_postgres_candidate.py` | Disposable CI SQL only |
| Append-only audit-table triggers and outbox | `key_approval_audit_guard_candidate.sql`, `key_audit_outbox_candidate.sql` | Owner/superuser can bypass or restore |
| At-least-once dispatcher with leases and per-namespace filtering | `audit_dispatch_candidate.py` | Explicit invocation, fake sink |
| Local receiver with event-ID idempotency | `audit_receiver_sqlite_candidate.py` | Separate local SQLite file, **not external/WORM** |
| Signed delivery with HMAC-SHA256 | `signed_audit_transport_candidate.py` | In-process test keys, no transport/TLS |
| Pinned signing-key rollover and revocation | `audit_key_rotation_candidate.py` | Thread-serialized **in-memory** keyring, no durable tombstones |
| Retry-exhaustion visibility | `audit_outbox_health_candidate.py` | Read-only counters, no alerts |

Most recent evidence: [Finance OS CI #145](https://github.com/V1P3eR1/Core8-AI/actions/runs/45189237936)
passed **172 tests** in the disposable PostgreSQL job; [Secret Scan #618](https://github.com/V1P3eR1/Core8-AI/actions/runs/45189237914) passed.
These CI checks do not constitute a penetration test or production security certification.

## Non-negotiable production blockers

1. **Operator identity:** choose production OIDC/IdP; validate issuer, audience,
   signing algorithms, subject and membership on every privileged action.
   Obtain a separate administrative authorization review.
2. **Trusted secrets and key rotation:** choose KMS/HSM/Secrets Manager, split
   sender/receiver access, protect key version IDs, revoke and audit credentials,
   and persist verified keyset/tombstone state outside process memory. No live
   secret may be committed into this repository.
3. **Independent anti-rollback floor:** deploy a separately administered,
   authenticated, durable CAS service (not a replica of the finance database);
   validate crash and restored-backup cases. Create and rehearse an
   operator-approved floor-ahead/database-behind recovery workflow that never
   lowers the floor.
4. **Approval issuance and least-privilege DB accounts:** trusted dual-operator
   workflow, atomic consume-once ledger, separate DB roles for provisioning,
   consuming, audit reading and exporting; deny production API database accounts
   administrative privileges. Execute provisioning and lifecycle tests.
5. **Independent audit sink:** choose external append-only/WORM retention,
   authenticated delivery, TLS, receiver-side durable idempotency and
   namespace segregation; test replay, partial outages and backup recovery.
6. **Operational monitoring:** alert on exhausted delivery attempts, increasing
   pending age, signature failures and key-transition mismatch; set on-call
   ownership and incident escalation. Add audited manual requeue workflow.
7. **Real tenant isolation:** enforce PostgreSQL RLS for every production query,
   verify against separate tenants using production-equivalent DB roles,
   and run negative auth and cross-tenant integration tests.
8. **Release controls:** security/privacy review, secrets scan, dependency and
   SAST review, protected CI, infrastructure change review, staged test rollout,
   rollback drill and explicit release-owner approval. Preserve finance endpoint
   503 until all controls pass. Enable neither Stripe writes nor live webhook
   effects without separate authorization.

## Completion definition

The Sandbox code work is complete **only** where implemented controls have
passing CI; release is **NOT ready** until each production blocker has a
named service owner, deployment-specific evidence, reviewed change, and
independent security sign-off. Documentation or a mock service is not evidence
that an external provider, credential, role or WORM archive was configured.

**Forbidden without explicit approval:** merging PR #64, deploying to production,
changing production DB/KMS/identity settings, enabling Finance API/Stripe live
writes, or sending production financial records to an audit destination.
