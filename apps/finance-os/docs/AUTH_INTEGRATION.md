# Finance OS — identity and tenant authorization integration contract

**Status: DRAFT. Not wired to requests, not production-ready.**

## Current implementation

- `tenant_access.py` is a standalone **policy decision function**. It does not parse, authenticate, verify or mint JWTs; it has no dependency on Stripe or production credentials.
- `VerifiedFinancePrincipal` is an internal data contract. **Constructing this dataclass does not authenticate anyone.** Its name is conditional on an external trusted verifier, not proof on its own.
- Role matrix: viewer → read; analyst → read, review; operator → read, review, operate. Every check requires **exact tenant equality**. No super-admin bypass, wildcard or implicit role escalation.
- `/finance/overview` remains disabled with HTTP 503 even if a caller supplies `Authorization`, `X-Tenant-ID`, `X-Role` or `X-Is-Admin`.
- Merchant ingress is **not user authorization**: the Stripe webhook uses an independently configured, single merchant-to-tenant binding after raw-payload signature verification; this does not confer customer-facing access.
- PostgreSQL composite foreign keys prevent mismatched tenant assignment in the operational activity table, **not** arbitrary cross-tenant SELECT access.
- `tenant_queries.py` now contains a **non-routed**, read-only aggregate query that calls `require_finance_permission` *before* querying and applies `WHERE organization_id = %s` with a positional parameter. This is defense in depth for the prototype, not a claim that caller-supplied `VerifiedFinancePrincipal` objects are authenticated.
- Real PostgreSQL tests with two synthetic tenants, and unit tests rejecting invalid principals before SQL, passed in [Finance OS CI #55](https://github.com/V1P3eR1/Core8-AI/actions/runs/45130043934); [secret scan #341](https://github.com/V1P3eR1/Core8-AI/actions/runs/45130043925) passed. **RLS and verified identity remain TBD.**

## Contract for a future verified identity adapter (NOT IMPLEMENTED)

1. Validate issuer, audience, algorithm allowlist, signature, expiration, not-before, token type, and key rotation using the chosen trusted OIDC provider / validated platform auth service. Never accept `alg=none`, user-controlled JWK URLs, unsigned headers, claims decoded without signature verification or client-supplied role/tenant headers.
2. Resolve an **active server-side tenant membership** from the application's authoritative store, independently of request body, Stripe event metadata, mutable email address, or free-form JWT tenant claim.
3. Map immutable verified subject + tenant + server-side role to a `VerifiedFinancePrincipal`. Prefer an immutable subject rather than an email-derived identity; revoke on disabled/deleted membership.
4. On every financial read/review/operation, use `require_finance_permission(principal, tenant_id=resource_owner_tenant, action=...)` **after** resolving resource ownership from a trusted server-side source. Never let a caller select an arbitrary tenant by changing only a query parameter.
5. Enforce tenant filters in SQL (`WHERE organization_id = %s`) **and** add database row-level security / restricted roles before exposing multi-tenant endpoints. Validate unauthorized reads, updates, joins, errors and pagination as well as authorized operations.
6. Record least-privilege, privacy-safe audit metadata (principal ID, action, tenant, result, timestamp) in a protected audit sink with retention policy. Never log raw bearer tokens, Stripe payloads or full customer financial records.
7. Introduce operator approval and two-person review where required by the owner's financial risk policy. A role check **alone** must not authorize live charges, refunds, payroll or replay.

## Test and review checklist

- Existing policy-only tests exercise viewer / analyst / operator behavior; unknown, disabled, malformed and cross-tenant principals fail closed.
- HTTP regression tests ensure untrusted headers cannot enable the still-disabled Finance endpoint.
- PostgreSQL tests validate cross-tenant referential integrity, retry isolation and worker concurrency on disposable data.
- **TBD:** Real OIDC discovery/JWKS configuration, trust boundary verification, memberships and revocation tests, row-level security tests, operator auditing, secrets provisioning and full threat model.
- **TBD:** Trusted Stripe sandbox account mapping, genuine provider-generated signed webhooks and replay approval workflow.
- **TBD:** Human review of Israeli accounting, tax, fiscal invoices and payroll dependencies.

**Approval gate:** All of the above must pass independent security review before changing the 503 endpoint or deploying. No merge, live Stripe use or real-customer data is authorized by the presence of this document.


## Read-only PostgreSQL RLS candidate — validated in disposable CI

- [sql/rls_readonly_candidate.sql](../sql/rls_readonly_candidate.sql) defines a **review-only** read-only policy for `finance_stripe_event_inbox` and `finance_activity` based on a database-administrator-maintained `finance_rls_role_bindings` table and PostgreSQL `current_user`; the application/request cannot grant itself a role or write a mapping. This SQL is **not applied by** the regular sandbox bootstrap and is **not** a production migration.
- [tests/test_rls_postgres.py](../tests/test_rls_postgres.py) creates disposable PostgreSQL `NOLOGIN NOSUPERUSER NOBYPASSRLS` roles, provisions two synthetic tenant memberships, enables `FORCE ROW LEVEL SECURITY` temporarily, verifies disjoint read visibility in *both* operational tables, rejects unauthorized UPDATEs/binding mutations and removes the test policies and roles afterward. [Finance OS CI #58](https://github.com/V1P3eR1/Core8-AI/actions/runs/45131882227) **success**; [secret scan #370](https://github.com/V1P3eR1/Core8-AI/actions/runs/45131882214) **success**, commit `786d4fb`.
- **Important limitation:** The tested CI administrator is a superuser and may `SET ROLE` for fixtures. Live application credentials must be separate non-owner, non-superuser, non-BYPASSRLS roles without the ability to `SET ROLE` into another tenant. Provisioning identity-to-database-role mapping requires verified server-side membership, audited least privilege, migrations and a separate ingress/worker policy. The prototype currently has none of these capabilities.
- The candidate purposefully has **no write policy**, so applying it to a deployed writer/worker would break normal ingestion. Do not run its DDL on a shared, deployed or production database. Do not infer broad tenant isolation from an isolated SQL demonstration.
- Before any release: test unauthorized SQL SELECT and mutation across joins, connection-pool role reset, role-grant escalation, migration rollback, background worker execution and idempotent Stripe webhook ingress under distinct least-privilege roles. Keep `/finance/overview` disabled pending verified identity and authorization.


## Connection reuse / session identity regression — 2026-11-23

- [test_rls_postgres.py](../tests/test_rls_postgres.py) now checks sequential, transaction-scoped `SET LOCAL ROLE` switching on **one reused physical PostgreSQL connection** in disposable CI. Each synthetic tenant sees only its own event ID, and `current_user` resets when its transaction closes. This catches accidental transaction-level role leakage in the tested scenario.
- [Finance OS CI #60](https://github.com/V1P3eR1/Core8-AI/actions/runs/45139232196) **SUCCESS**, [secret scan #373](https://github.com/V1P3eR1/Core8-AI/actions/runs/45139232177) **SUCCESS** on commit `abdb130`.
- This is **not** testing a production connection pool, actual OIDC identities or live role provisioning. Application credentials must never be granted the ability to `SET ROLE` into arbitrary tenants; using pooled sessions requires explicit isolation controls, reviewed lifecycle cleanup, and penetration tests before exposure.


## Server-side membership candidate — 2026-11-23

- [membership_candidate.py](../membership_candidate.py) adds an **unwired** lookup of active tenant membership by an upstream-verified immutable subject and an explicit tenant ID. It rejects missing, disabled, ambiguous and unknown-role memberships. An authenticated identity source **is not implemented**: `TrustedSubject` is a data contract and is forgeable if constructed from untrusted inputs; never accept it from user-supplied fields or raw decoded JWTs.
- [sql/membership_candidate.sql](../sql/membership_candidate.sql) defines a disposable/test-only membership table (server-controlled rows, default disabled, no public grants), **not a production migration**.
- [test_membership_candidate.py](../tests/test_membership_candidate.py) exercises permission escalation, invalid principal values, missing memberships and role downgrades; [test_membership_postgres.py](../tests/test_membership_postgres.py) exercises server-side membership revocation and two fictional tenants with a transaction rolled back after testing.
- **Verified:** [Finance OS CI #65 — success](https://github.com/V1P3eR1/Core8-AI/actions/runs/45139726594) and [secret scan #390 — success](https://github.com/V1P3eR1/Core8-AI/actions/runs/45139726622), tested commit `ac85fd8`.
- **Remaining:** connect to a trustworthy OIDC verifier and centrally provisioned membership store with active/revoked state; enforce least-privilege database roles/RLS on every financial read/write; test token expiry, revocation, membership changes and session reuse; ensure existing finance API remains disabled before security review. No production access or live payments are enabled.


## Offline issuer-pinned JWT signature candidate — 2026-11-23

- [oidc_candidate.py](../oidc_candidate.py) validates RS256 JWT signatures against an **operator-provided, pinned** RSA JWKS. It checks strict HTTPS issuer, intended audience, required `iss/sub/aud/exp/iat/nbf` claims, bounded clock skew, single matching key ID, token size and unsafe header key-location rejection. It never trusts token-provided URLs, decoded-but-unverified claims or HS256 keys.
- [test_oidc_candidate.py](../tests/test_oidc_candidate.py) signs ephemeral RSA test JWTs and covers incorrect signatures, future/expired claims, audience/issuer mismatches, key selection and algorithm substitution. An additional test verifies that a validly signed token **still cannot bypass server-side membership or RBAC**, using a mock membership store; it does not establish real identity or tenant revocation in a deployed service.
- [Finance OS CI #70](https://github.com/V1P3eR1/Core8-AI/actions/runs/45140617247) **SUCCESS** on commit `61f03d0` (unit, disposable PostgreSQL and container build); the secret scan for this commit must be confirmed separately.
- **Trust boundary:** Configuration comes from the server; a malicious caller may not choose `issuer`, `audience` or `jwks`. This is an offline cryptographic validation candidate, **not full OIDC integration**: no discovery, trusted JWKS refresh/rotation/revocation service, token type and authorized client policy, active user session revocation, authentication endpoint, finance API route, or audited authorization layer has been implemented.
- Do not deploy the candidate or open `/finance/overview`. Before any rollout, select the external identity provider, pin and review its discovery/JWKS policy, validate token profile and identity subject, connect authoritative memberships with revocation, enforce privileged DB isolation and complete security review.


## Offline token type separation — 2026-11-23

- The sandbox `oidc_candidate.py` now rejects otherwise valid signed JWTs unless `token_use=access`. A JWT with `token_use=id` or no `token_use` cannot be substituted as an API access token. Tests use only ephemeral RSA keys and mock issuer/claims.
- [Finance OS CI #73 — SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45141385728) and [secret scan #416 — SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45141385718), commit `c818b6e`.
- **Provider compatibility gate:** `token_use` is a candidate-specific assertion, not a universal OIDC access-token claim. A real identity provider may use a different token-type profile; adopt its formally verified access-token semantics (including audience/client and token type), and update tests before enabling any API. Never relax token-type discrimination to make a mismatched provider work.
- The module remains disconnected from HTTP endpoints and financial data access; no actual OIDC discovery, secure key rotation, login, logout or token revocation has been built.


## Offline JWT bounds and issuer hardening — 2026-11-23

- The unexposed `oidc_candidate.py` now applies a **candidate-specific maximum signed lifetime of 15 minutes** (`exp - iat <= 900s`), requires integer numeric date claims, rejects malformed HTTPS issuer URLs with credentials/query/fragment, refuses unsupported JWT `crit` headers and RSA verification keys below 2048 bits.
- [Finance OS CI #76 — SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45143735890) and [secret scan #419 — SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45143732786), tested commit `43dff54`. Tests include overlong/invalid token timestamps, malicious issuer strings, critical JWT headers and a 1024-bit RSA test key.
- **Important integration constraints:** The 15-minute lifetime is a conservative candidate policy, not a published commitment by any external identity provider. A real issuer may have a different access-token profile; its algorithm, token lifetime, audience, client validation, JWKS rotation, revocation, and operational controls require documented security review. Do not weaken protections merely to make an incompatible provider pass.
- This is *offline test-only validation*: no real OIDC discovery, network key fetch, finance endpoint authorization, customer data or live Stripe functionality was added.


## Pinned JWKS key rotation and emergency key withdrawal — 2026-11-23

- [tests/test_oidc_candidate.py](../tests/test_oidc_candidate.py) now exercises an **offline operator-approved key rotation overlap** using two newly created ephemeral RSA test keys. During overlap both old/new signed tokens verify against the pinned JWKS; after removing the old key, its token is rejected even before its own expiry. It also rejects unknown/duplicate key IDs and a token-supplied `jwk` public key.
- [Finance OS sandbox CI #78 — SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45144128133) and [secret-scan #422 — SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45144128151), tested commit `41cd2a2`.
- These are **unit tests of changed trusted JWKS input**, not an implemented OIDC key lifecycle. A provider-approved rotation process, signed/validated discovery configuration, key refresh bounds, emergency invalidation, replay safety and independent runbook review remain `TBD`. A JWT must never choose its own JWKS URL or signing key.
- There is no connected identity provider, authenticated finance API or financial transaction enabled by these tests. The PR remains draft-only.


## In-memory pinned JWKS approval/retirement candidate — 2026-11-23

- [pinned_jwks_candidate.py](../pinned_jwks_candidate.py) adds an **unwired, in-memory-only** operator-input candidate with isolated read snapshots, atomic replacement, strictly monotonically increasing generation numbers, immutable key material for an existing `kid`, and key tombstones preventing withdrawn keys from reappearing within one running process. It validates supported public RSA signing-key structure and rejects private-key components. It does not fetch arbitrary internet resources or accept JWT-specified JWKS locations.
- [tests/test_pinned_jwks_candidate.py](../tests/test_pinned_jwks_candidate.py) exercises overlap, withdrawal, old-key token invalidation, stale approval rejection, same-`kid` replacement, caller snapshot mutation, private JWK components, malformed keys and duplicate IDs. [Finance OS CI #81 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45145384585) and [secret scan #434 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45145384433), tested commit `44173a3`.
- **Critical limitation:** this is **not** a durable key registry, automatic key rotation, independent operator authorization, network JWKS validation, revocation service, or production security boundary. Restarting the process loses both generation history and tombstones. The registry accepts only local, trusted operator-provided public keys and must never receive keys from request parameters or JWT headers.
- **Release gates:** audited two-person authorization policy where appropriate, durable tamper-evident rollback prevention, safe distribution of approved key versions to all services, verified issuer discovery / cache staleness and emergency key revocation procedures, real provider compatibility and identity/RBAC audit. Do not integrate with the still-disabled finance API until independently reviewed.


## Authenticated JWKS snapshots and recovery gate — 2026-11-23

- [jwks_state_candidate.py](../jwks_state_candidate.py) adds a **sandbox-only, offline** authenticated export/import for the in-memory `PinnedJwksRegistry`. Its snapshot contains public JWKs, key-generation number and the retired-key tombstone list; integrity is verified with HMAC-SHA256 under a separately supplied 32+ byte key. Invalid/modified snapshots and incorrect keys fail closed.
- Import requires a `minimum_generation` **supplied by a separate, trusted, durable monotonic source**. A signed snapshot without that external high-watermark can be replayed after an old-key revocation. The candidate neither persists the high-watermark nor provides atomic, durable storage or an authorized operator workflow.
- [tests/test_jwks_state_candidate.py](../tests/test_jwks_state_candidate.py) verifies signed round-trip recovery, retired-key rejection after recovery, stale-version rejection with the trusted floor, tampering, wrong signing key, malformed signed data and invalid signing-key input. [Finance OS CI #84 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45146150755) and [secret scan #441 SUCCESS](https://github.com/V1P3eR1/Core8-AI/actions/runs/45146150502), tested commit `554dbea`.
- **Security warning:** This is not a production backup, tamper-evident audit system, HSM-backed signer, transactional state store or complete anti-rollback guarantee. Implement a strongly protected independent generation floor and atomic updates (plus restore, permission, concurrency, compromise and crash testing) before any integration. Do not make the generation floor client-controlled.
- The finance API remains disabled, no provider network integration or new database credentials were added, and no merge/deployment/live financial action is authorized.
