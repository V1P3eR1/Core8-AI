# FastAPI tenant authorization gate — findings and safe integration path

Inspected main branch:
- `apps/core8-platform/backend/security/jwt_auth.py` generates JWT access claims `sub`, `email`, `role`, `iat`, `exp`, `type`. **There is no tenant_id claim.**
- `require_jwt` checks bearer token and access-token type, but does not resolve tenant membership.
- `require_admin` checks the admin role only; admin does not automatically authorize access to every customer tenant.
- `apps/core8-platform/backend/database.py` uses SQLite/`aiosqlite`; its `leads` table contains `tenant_id` and globally primary-keyed `id`. No source-submission uniqueness constraint was observed in that table.
- The Social Manager's internal `sm_*` tables are not multi-tenant by default.

## Required before adding any live ingestion endpoint

1. Create a server-side, auditable mapping of authenticated user IDs to tenant IDs and permissions, e.g. `tenant_memberships(user_id, tenant_id, role, active)`, with explicit authorization checks. Never infer membership from request `tenant_id`, email domain, JWT `role`, or a client-provided header.
2. For inbound webhook sources, authenticate the source separately (signature, timestamp, replay defense) and map the verified integration credential to exactly one tenant; an anonymous webhook is **not** a JWT user.
3. Resolve an authorized `trusted_tenant_id` before invoking the canonical validator or idempotency transaction. Deny by default when no membership exists. Never expose existing lead identifiers from other tenants.
4. Add a dedicated, versioned SQLite claim table through the project's reviewed migration path; insert the lead and idempotency claim in the same transaction. Existing demo code is intentionally isolated and not a drop-in migration.
5. Build an authenticated `POST /api/leads/intake` behind a feature flag, with request-size limit, rate limiting, verified consent, source provenance and audit trail.
6. For reviewer approval, check membership and permissions server-side. Do not trust the browser's fictional reviewer role from the preview.
7. Run integration tests: missing token (401), wrong role (403), wrong tenant (403/404), invalid signature, replay, consent failure, concurrent same-key requests, crash/retry, and no outbound effects.
8. Perform security review and explicit production authorization before any merge/deploy.

## Decision

**Do not expose an intake API yet.** A route protected by the current JWT dependency alone would create a false sense of tenant authorization. The next implementation step is a standalone tenant resolver and negative tests using synthetic identities, followed by an isolated FastAPI TestClient harness. No live data or external network calls.
