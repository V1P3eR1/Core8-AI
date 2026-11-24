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


## File-backed generation floor (disposable SQLite sandbox) — 2026-11-23

- [sqlite_generation_floor_candidate.py](../sqlite_generation_floor_candidate.py) implements the abstract `IndependentGenerationFloor` interface against a separate local SQLite file, **not** the Finance PostgreSQL database. It provides explicit one-time test namespace provisioning, read-only recovery of existing versions, atomic conditional UPDATE (CAS) and fail-closed errors for missing/corrupted storage, invalid namespaces, bad generations or missing rows. There is no API, scheduler, network transport, credential management or production grant.
- [tests/test_sqlite_generation_floor_candidate.py](../tests/test_sqlite_generation_floor_candidate.py) exercises persistence after reopening the file, independent namespaces, six simultaneous CAS attempts with exactly one success, malformed inputs and missing schema. It also **proves an important limitation**: restoring an old copy of the SQLite file restores its prior generation. SQLite is therefore **not an independently authenticated or tamper-resistant external watermark service**.
- [tests/test_audit_keyring_store_postgres.py](../tests/test_audit_keyring_store_postgres.py) checks real disposable PostgreSQL integration with the file-backed floor. A rotated, signed PostgreSQL state recovers through a reopened SQLite floor; restoring the old signed PostgreSQL row alone is denied because the distinct SQLite file retains the advanced generation.
- **Verified:** [Finance OS CI #169 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45261475424), [Secret Scan #693 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45261475430), tested commit `fd355ab`.
- **Still blocked for production:** SQLite can be rolled back by anyone with file/backup control, is local to the host and is not separately administered. Do not mistake a separate file for an independent durable trust authority. A production solution needs authenticated remote CAS, an independently controlled monotonic anchor, least-privilege callers, key management, secured backup/restore process, tamper evidence and audited failure recovery. No production merge, deployment, finance API or payment activity.


## Read-only floor mismatch diagnostics — 2026-11-23

- [audit_floor_diagnostics_candidate.py](../audit_floor_diagnostics_candidate.py) adds a trusted-operator, **read-only** diagnostic for comparing the separately supplied floor generation to the signed PostgreSQL audit keyring row. It reports only namespace, floor and DB generation, and one of: `healthy`, `floor_ahead`, `database_ahead`, `snapshot_invalid` or `missing_database_state`. It does **not** lower the generation, repair data, expose keys/snapshot bytes or create an HTTP endpoint.
- [tests/test_audit_keyring_store_postgres.py](../tests/test_audit_keyring_store_postgres.py) verifies the diagnostic returns each status against disposable PostgreSQL and an independently stored SQLite floor. It also verifies invalid/untrusted floors fail closed.
- **Verified:** [Finance OS CI #172 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45262568472), [Secret Scan #701 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45262568316), code commit `a3bc13e`.
- **Still release-blocked:** The SQLite floor is local and can be restored; no remote authenticated monotonic anchor, operator IdP, KMS, independently immutable audit service, privileged rescue workflow, production tenant authorization or security sign-off. Diagnostics must not become a publicly reachable endpoint without trusted operator authorization.


## Unwired remote floor service protocol candidate — 2026-11-24

- [remote_generation_floor_candidate.py](../remote_generation_floor_candidate.py) implements the abstract floor contract through an **injected transport**, with exact response-shape and namespace validation, bounded generation checks, HTTPS-only configured endpoint validation, explicit request timeout parameter, and rejection of ambiguous acknowledgments, malformed replies and transport errors.
- [tests/test_remote_generation_floor_candidate.py](../tests/test_remote_generation_floor_candidate.py) uses a purely in-process fake transport. Tests exercise read, successful CAS, conflicting CAS, invalid namespace/generation, malformed response, unavailable transport and unsafe endpoint. [tests/test_audit_keyring_store_postgres.py](../tests/test_audit_keyring_store_postgres.py) additionally tests the adapter through the signed audit-keyring/PostgreSQL coordinator.
- **Security limitation:** There is no actual HTTP client or remote server in this candidate. The injected transport is responsible for independently verifying TLS peer identity, client authentication, timeouts, no redirects, service authorization, non-replayable writes and linearizable durable storage. Merely configuring an `https://` URL does **not** provide any of those guarantees. A fake transport must never be treated as the production high-watermark authority.
- **Production release remains BLOCKED:** independently administered remote service, trusted identity provider and credentials, immutable anti-rollback anchor, real KMS, operational alerting, network fault-injection and deployment-specific security review have not been configured. No branch merge, public Finance API activation, production migrations or payments.


## Optional mTLS HTTPS floor-client transport (Sandbox) — 2026-11-24

- [https_floor_transport_candidate.py](../https_floor_transport_candidate.py) supplies a **disabled-by-default adapter** implementing the injected transport contract for the remote floor. Its configured operator-managed hostname, CA bundle, client certificate and private-key file define TLS server-verification, mutual TLS and minimum TLS 1.2. All connections are synchronous `http.client.HTTPSConnection` calls with maximum five-second timeout, exact hostname/port/path, no proxy or redirect handling and no automatic retries.
- The request is JSON POST to `/v1/floor` with a strict operation/namespace/version shape and maximum size; only HTTP 200, exactly `application/json`, nonempty JSON object response up to 4 KiB and no duplicate JSON keys are accepted. The higher-level [remote_generation_floor_candidate.py](../remote_generation_floor_candidate.py) separately validates response status, namespace and CAS acknowledgment.
- [tests/test_https_floor_transport_candidate.py](../tests/test_https_floor_transport_candidate.py) uses *network-free* mocked TLS context and HTTP connection to cover valid read/CAS exchange, reject redirects, 401/202/204 responses, bad content-type, oversized/malformed/duplicate-key JSON, bad host/path/credential URL and malformed CAS arguments. The synthetic certificate filenames are not real credentials.
- **Verified:** [Finance OS CI #181 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45355203743), [Secret Scan #716 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45355203637), code commit `428489e`.
- **Production blockers remain:** No external floor service or actual end-to-end mTLS handshake has been deployed or tested; the HTTP transport is not wired to a running worker. Connection establishment, DNS trust, client key storage and rotation, provider-side strong caller authorization, response freshness and integrity, durable linearizable CAS, network fault injection, independent irreversible anti-rollback anchoring, monitoring and independent review must be implemented and demonstrated. HTTPS/mTLS alone does **not** ensure server-side storage is immutable, sufficiently independent or resistant to rollback. No live keys, merge, deployment or payment processing.


## Lost CAS acknowledgment read-only reconciliation — 2026-11-24

- [audit_cas_reconciliation_candidate.py](../audit_cas_reconciliation_candidate.py) performs a **single, read-only** query against a trusted `IndependentGenerationFloor` after the original CAS response is lost or times out. It returns `unchanged`, `advanced_or_later` or `unavailable` without mutating PostgreSQL, retransmitting CAS, lowering the floor or inferring who advanced it. Invalid or rolled-back observations fail closed.
- [tests/test_audit_cas_reconciliation_candidate.py](../tests/test_audit_cas_reconciliation_candidate.py) simulates a server commit followed by a lost ACK; the follow-up causes exactly **one CAS and one READ**, never a duplicate CAS. Other tests cover an uncommitted request, concurrent third-party advancement, unavailable floor, invalid inputs and floor rollback.
- The [remote floor protocol candidate](../remote_generation_floor_candidate.py) now rejects a `conflict` reply when the observed generation has **not** moved beyond the caller's expected value. Its regression suite checks this contradictory server response.
- **Verified:** [Finance OS CI #186 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45355953878), [Secret Scan #721 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45355953865), tested commit `b32f598`.
- **Critical limitation:** Even a trusted floor reading `advanced_or_later` cannot attribute the version increase to the lost CAS attempt. Human/independently authorized reconciliation of the intended signed DB state is required before continuing; this diagnostic is not authorization to replay or repair. No actual remote service, authentic network exchange, production identity/KMS, external WORM store or release sign-off exists.


## Floor-ahead incident recovery preflight (read-only) — 2026-11-24

- [audit_recovery_preflight_candidate.py](../audit_recovery_preflight_candidate.py) adds a **read-only operator preflight** for the one-generation gap where a trusted independent floor advanced but the PostgreSQL keyring write failed. It does not update keys, DB rows, credentials or the floor, and does not expose raw secret material.
- The preflight requires a `floor_ahead` diagnosis with exactly a one-generation gap, validates the existing DB snapshot using its own old generation **without granting it signing authority**, validates a separately supplied proposed signed keyring snapshot against the newer floor generation, checks monotonic revoked-key tombstones, dropped-key history and unchanged key bytes for reused IDs, and rereads the floor to catch a concurrent advance. The output contains `review_required`, exact generations and the proposed snapshot SHA-256 fingerprint. It is never an authorization or a transaction lease.
- [tests/test_audit_keyring_store_postgres.py](../tests/test_audit_keyring_store_postgres.py) verifies that a valid proposed snapshot produces a review-only result while leaving both PostgreSQL and the floor unchanged. Tests reject a healthy system (no need to recover), a tampered blob, an unrelated but signed keyring, and a gap larger than one generation.
- **Verified:** [Finance OS CI #189 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45390050653) and [Secret Scan #728 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45390050316), tested code commit `3858e25`.
- **Critical production blockers:** The code cannot verify who authorized or created the proposed snapshot. A valid MAC alone does not establish dual-operator approval, incident provenance, external audit record or immutable trust. Incident owners must independently authenticate source evidence and approvals, confirm no concurrent mutations, revalidate under actual DB transaction and floor locks, then use an independently reviewed recovery mechanism. **No automatic repair has been implemented.** No KMS/IdP, external floor service or WORM audit sink is deployed; do not merge or enable production.
