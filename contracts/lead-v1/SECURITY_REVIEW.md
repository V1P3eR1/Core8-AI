# Security review and production readiness — Lead Intake v1

**Status:** Offline proof of concept; NOT production-ready. Reviewed 2026-11-23.
**Scope:** `contracts/lead-v1/` only. No deployed endpoint or database migration.

## Confirmed controls (offline fixtures)

- Server-side synthetic credential registry maps key IDs to tenant/source; caller-supplied tenant identity is ignored.
- HMAC-SHA256 verifies timestamp and raw body, with 300-second freshness and constant-time digest comparison.
- Optional bounded previous-key grace period; inactive keys rejected.
- SQLite `BEGIN IMMEDIATE` atomically commits lead, submission claim and delivery receipt; concurrency tests assert single acceptance.
- Consent is required; tenant/source-scoped idempotency and payload-conflict checks.
- FastAPI TestClient exercises HTTP error handling and 64-KiB streamed body limit.
- CI includes isolated Python/Node tests and secret scanning.

## Blocking findings before any public endpoint

**P0 — Delivery ID not authenticated.** Current `webhook_signature_demo.signature` signs `timestamp + "." + raw_body` but **does not sign `delivery_id`**. An attacker with a valid signed payload could change the delivery-ID header and bypass the *delivery receipt* uniqueness check; lead submission idempotency still protects against duplicate lead rows for the same submission ID. Fix by authenticating delivery identity under an explicitly versioned provider-specific signature protocol (or by deriving receipt identity from a cryptographically authenticated provider event ID). Add tamper tests. Do not claim full cryptographic replay protection until resolved.

**P0 — Tenant membership and production credentials absent.** Production JWT has no verified tenant membership binding. Require server-side tenant membership authorization for dashboard actions; map inbound provider credentials to tenants using a protected server-side store, never a request-body claim. Define rotation/revocation and audited access.

**P0 — No production integration.** The fixture uses synthetic keys and in-memory SQLite; it is not connected to actual backend routes. Plan and review SQLite schema migrations, constraints, rollback, backups and tenant isolation before deployment.

**P1 — Shared fixture DB connection.** The FastAPI fixture shares one SQLite connection across requests (`check_same_thread=False`), which is not a safe production concurrency architecture. Use per-request connections with transactions, busy timeout, WAL as appropriate, and parallel HTTP tests.

**P1 — HTTP fixture is not hardened for the internet.** Add verified provider adapters, proxy/header trust policy, ingress rate limits, operational metrics, safe logging/redaction, bounded JSON nesting/field validation, and consistent failure response semantics. Do not expose synthetic credential identifiers or test routes publicly.

**P1 — Credential rotation operations.** Require secret storage, per-provider key versioning, strict expiry, emergency revocation, audit trail and provider protocol compatibility.

**P1 — Privacy and retention.** Define consent evidence, minimization, data retention/deletion, and access logs before storing customer PII.

## Exit criteria

1. All CI checks pass and security tests include tampered delivery-ID replay.
2. A reviewed provider signature scheme binds every replay-sensitive identity.
3. Tenant authorization and production credential storage pass negative tests.
4. Migration/rollback plan and concurrency/load tests pass on an isolated staging database.
5. Privacy/retention and monitoring reviewed.
6. Explicit approval before merging, production deployment, or real-customer traffic.
