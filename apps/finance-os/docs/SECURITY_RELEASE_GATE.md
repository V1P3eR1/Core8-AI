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


## Audit key-state crash/restart recovery candidate — 2026-11-23

- [audit_key_state_candidate.py](../audit_key_state_candidate.py) adds a canonical HMAC-authenticated **metadata-only** snapshot for the in-memory audit signing keyring. It stores active and verification-only key IDs, removed-key tombstones, namespace, generation and independently keyed secret-identity proofs. **It does not serialize delivery secret bytes.** To restore it, the caller must supply trusted independently provisioned secret bytes and a matching independently verified minimum generation.
- `recover_audit_keyring_with_floor` insists on the `IndependentGenerationFloor` abstract contract and fails closed on invalid, missing or inconsistent floor values or provider errors. Import requires the snapshot generation to match the provided trusted floor exactly; this is stricter than accepting any older signed state. The abstract type does **not** authenticate its implementation: a fake or untrusted floor must never be passed from user-controlled code.
- [tests/test_audit_key_state_candidate.py](../tests/test_audit_key_state_candidate.py) covers reboot with tombstone preservation, overlap verification keys, proof mismatch on incorrect secret, signed-state mutation, namespace substitution, older/newer generation mismatch, malformed provider response and floor-service outage.
- **Verified:** [Finance OS CI #149 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45190622078), [Secret Scan #634 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45190626642), commit `4506309`. Floor-adapter regressions passed in [Finance OS CI #151 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45190943699) with [Secret Scan #637 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45190943843), tested commit `6f943f1`.
- **Release is BLOCKED:** No durable separate audit-key state store, independently administered authenticated floor, production KMS, secret provisioning or credential rotation has been configured. A MAC-signed backup alone **cannot** prevent rollback if the attacker also restores the floor. Requires review of independent storage and tested operator recovery.


## Signed audit-keyring inventory restore candidate — 2026-11-23

- [audit_keyring_state_candidate.py](../audit_keyring_state_candidate.py) exports HMAC-authenticated **metadata only** (active key ID, SHA-256 of independently trusted key bytes, verification-key IDs, revoked/tombstoned IDs and generation). No secret bytes are stored in the snapshot.
- Import requires the separately supplied snapshot-MAC secret, an **exact trusted external minimum/current generation** and an exact pinned mapping of key bytes from a trusted secret provider. It validates the authenticated inventory and content digests before reconstructing the in-memory `AuditKeyringCandidate` with its tombstones.
- [tests/test_audit_keyring_state_candidate.py](../tests/test_audit_keyring_state_candidate.py) checks valid restart simulation, overlap-key restore, key-material substitution denial, state tampering rejection, and **denial of replaying an old signed snapshot** when the external trusted generation has advanced.
- **Verified on commit `595a94c`:** [Finance OS CI #155 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45243415331) and [Secret Scan #642 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45243415575).
- **Still blocked for production:** no durable snapshot store, real KMS/HSM, independent authenticated CAS/high-watermark, approved operator identity, service identity or remote immutable audit sink. MAC signing keys and externally trusted key maps are supplied by caller in isolated tests. The snapshot file alone cannot defend against an external-floor rollback.


## PostgreSQL signed audit-keyring metadata store candidate — 2026-11-23

- [sql/audit_keyring_store_candidate.sql](../sql/audit_keyring_store_candidate.sql) adds a **disposable CI-only** PostgreSQL table storing the namespace, generation and HMAC-signed **non-secret** audit-key inventory snapshot. There are no KMS-managed key bytes or application grants in this schema.
- [audit_keyring_store_candidate.py](../audit_keyring_store_candidate.py) implements one-time bootstrap, separately trusted generation-checked recovery, and an UPDATE with `SELECT ... FOR UPDATE`/generation CAS that serializes concurrent writers. The update validates both current and proposed snapshot signatures and trusted key fingerprints, enforces generation advancement by exactly one, preservation of prior tombstones, and no silent key substitution.
- [tests/test_audit_keyring_store_postgres.py](../tests/test_audit_keyring_store_postgres.py) uses disposable PostgreSQL to test restart recovery after overlap and key revocation, stale external-generation denial, two competing writers with only one commit, a valid old snapshot restored into a newer database against an unchanged external floor, modified signature failure, duplicate initialization and rejection of caller-controlled nested transactions. The CI SQL fixture executes complete SQL rather than splitting on semicolons in comments.
- **Verified:** [Finance OS CI #161 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45250919924), [Secret Scan #663 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45250919948), code commit `5b149fd`.
- **Remaining production blockers:** This store is in the same PostgreSQL failure domain and does not independently maintain or authenticate a monotonic watermark. The `external_generation` argument is a trusted **caller-provided test value** and must not come from a request: a separately administered, durable CAS service must advance before the database write. A failure after that external CAS will intentionally cause fail-closed recovery requiring an audited manual workflow. KMS/HSM secret lookup, real authorization, production DB least-privilege permissions, external immutable audit service, security review and production deployment remain absent.


## Audit signing-key independent floor coordination candidate — 2026-11-23

- [audit_external_floor_candidate.py](../audit_external_floor_candidate.py) bridges the signed PostgreSQL audit-keyring metadata store to the **abstract** separately trusted `IndependentGenerationFloor` contract. It first reads an independently supplied floor, authenticates the current database snapshot, validates the proposed rotated state, tombstones and pinned key bytes, then advances the external floor with compare-and-swap **before** attempting the database write.
- The coordinator fails closed if generation is stale, key inventory is invalid, prior retirement is reversed, a caller-owned transaction is already open or the floor refuses advancement. A failure in PostgreSQL after the external CAS intentionally leaves the floor ahead of the database and subsequent recovery blocked; only an authorized audited operator recovery can repair it **without lowering the floor**.
- [tests/test_audit_keyring_store_postgres.py](../tests/test_audit_keyring_store_postgres.py) now simulates independent-floor success, stale signed-row rollback, invalid proposal before floor mutation, refusal by the floor CAS, and injected PostgreSQL write failure after a successful floor advance.
- **Verified:** [Finance OS CI #165 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45251562200), [secret scan #674 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45251562634), tested code commit `c199d89`.
- **Release remains BLOCKED:** The external floor used in these tests is a process-local fake. No independently administered linearizable durable floor is deployed or authenticated; no production KMS, operator authorization, immutable external audit store or recovery approvals have been connected. Do not merge or deploy this candidate.
