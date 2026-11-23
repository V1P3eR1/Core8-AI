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
