# Core8-AI lead interoperability — delivery plan

**Scope:** lead-triage intake → canonical lead → deduplication → human review → approved downstream handoff.  
**Repository:** V1P3eR1/Core8-AI, draft PR #85.  
**Safety:** no production merge, deployment, customer data, credential changes, real messaging, bookings or payments without explicit approval.

## Work packages

| ID | Deliverable | Dependency | Acceptance / exit gate | State |
| --- | --- | --- | --- | --- |
| P0 | Canonical lead schema and offline validator | none | Node tests, browser parity and tenant mismatch regression pass | Implemented in draft; CI passed on earlier commit |
| P1 | Lead Triage offline preview adapter | P0 | unsigned/verified inputs, invalid consent, immutable input tests | Implemented in draft; invalid consent now rejected; awaiting latest CI |
| P2 | Hebrew RTL browser sandbox | P0 | no network, no storage, no unsafe DOM API; four synthetic scenarios | Implemented in draft |
| P3 | Review state machine | P0 | reviewer, source, consent and tenant gates; no simulated sending | Implemented in draft |
| P4 | Tenant-scoped dedup preview | P0 | duplicate and cross-tenant collision tests | Implemented in draft |
| P5 | PostgreSQL idempotency design | P4 | unique key and transaction/retry acceptance criteria | Design only; no migration executed |
| P6 | Actual PostgreSQL integration in isolated test environment | P5 | concurrent inserts, crash rollback, retry and conflict tests on real DB | Not started |
| P7 | Authenticated tenant-aware API | P6 | server-derived tenant identity, negative auth/RLS tests, audit and rate limiting | Not started |
| P8 | Approved outbox handoff | P7 | explicit human approval, idempotent delivery, audit, no unauthorized sends | Not started |
| P9 | Cross-module integration and pilot | P8 | receptionist/social adapters, consent provenance, operator UAT, privacy review | Not started |
| P10 | Production readiness | P9 | security review, observability, backups, rollback, owner sign-off | Not started |

## Verified architecture discovery (2026-11-23)

Main branch currently uses **SQLite via aiosqlite** in `apps/core8-platform/backend/database.py`; `apps/core8-platform/backend/requirements.txt` has `aiosqlite` but no PostgreSQL driver, and `apps/core8-platform/backend/alembic.ini` was not found. Therefore `postgres-idempotency.proposal.sql` **must not be applied to the current backend**. Treat PostgreSQL as a separately evaluated migration path. A SQLite-compatible isolated prototype and explicit migration decision must precede any backend changes. The Social Manager also has admin-only access and internal tables lacking tenant IDs, so it must not be presumed ready for multi-tenant lead ingestion.

## Immediate implementation sequence

1. **P1 correctness:** completed in draft: malformed consent now fails closed; verify latest CI.
2. **P0 robustness:** extend malformed-input tests, ensure validator does not throw for unexpected shapes.
3. **P5 verification:** add SQL contract tests that statically verify uniqueness and transactional design; this is *not* a substitute for real DB tests.
4. **P6 preparation:** inspect current FastAPI/SQLite schema and decide whether to add an isolated SQLite prototype first or separately introduce PostgreSQL; no production schema changes without review.
5. **P6 execution:** run SQLite concurrency/idempotency tests in a disposable environment; only then evaluate PostgreSQL concurrency tests as a separate track.
6. **P7–P10:** implement sequentially with independent review and explicit authorization for external/production effects.

## Required integration decisions

- Confirm target backend and migration framework after code inspection; do not assume the draft contract maps to main.
- Define canonical payload hash and source-signature trust boundary.
- Define authoritative tenant resolver, database RLS and allowed service roles.
- Define contact consent provenance and retention/erasure rules.
- Define real downstream systems and human-approval ownership.

## Verification and reporting

Each increment: commit to draft branch → GitHub Actions checks → fix failures → update this plan and Notion project registry. Report **implemented**, **tested**, **proposed**, and **not started** separately. A passing secret scan does not establish full security. Do not merge or deploy automatically.

## Offline vertical slice (2026-11-23)

Added `offline_intake_demo.py` and `test_offline_intake_demo.py` to compose verified synthetic identity, explicit tenant membership, consent, source-verification fixture, deterministic demo digest and atomic SQLite lead/claim creation. Nine tests cover happy path, idempotent replay, conflicting payload, denied tenant/admin, unsigned source, missing consent and invalid input. **This is not a live FastAPI endpoint**. The `source_verified` boolean and `identity.verified` fixture are not cryptographic verification; never accept these from HTTP payloads. Real signature verification, authenticated membership storage and API integration remain blocked until implemented.

## Offline webhook signature verification (2026-11-23)

Added `webhook_signature_demo.py` and ten offline tests for HMAC-SHA256 over timestamp + exact request bytes, constant-time signature comparison, 5-minute freshness window, limited future clock skew and a 64 KiB body cap. The secret is a **synthetic fixture**. This is not an HTTP endpoint and does not implement tenant-to-credential mapping, durable nonce replay prevention, secret rotation or webhook provider-specific signature formats. Timestamp validation alone does not prevent replays within the allowed window; the existing idempotency claim is a separate requirement. No live webhook ingestion is authorized.

## Signed intake vertical slice (2026-11-23)

Added `signed_intake_demo.py` and `test_signed_intake_demo.py` (11 cases). The demo maps a synthetic credential ID through a **trusted in-process registry** to one tenant and source, verifies the exact request bytes with HMAC, enforces timestamp freshness and explicit consent, then performs SQLite atomic claim + lead creation. The request's claimed tenant is ignored. Duplicate submission IDs replay the original lead and changed payloads conflict. **No HTTP route, credential persistence, credential rotation, nonce store, request rate limiting or production secrets are included.** A signed request can still be replayed within the 5-minute window; duplicate lead creation is blocked by the idempotency claim but event replay prevention requires additional work. Only fixture data is used.

## Credential rotation policy fixture (2026-11-23)

Added `credential_rotation_demo.py` with nine tests: active/current secret, bounded previous-key grace period, expiry, unknown key, inactive credential, old timestamp, tampering and malformed grace period. **This is a standalone policy fixture and is not wired into `signed_intake_demo.py` or `webhook_receipt_demo.py` yet.** Actual secret persistence, audit logging, rotation scheduling, per-provider signature semantics and emergency revocation remain unimplemented. The previous key must be removed after the grace period; never accept a previous key indefinitely.

## Rotated credentials in atomic webhook intake (2026-11-23)

Wired `verify_rotating_credential` into the offline `webhook_receipt_demo.py` before any database mutation. Added six integration tests for old/new key acceptance, expiry, rejection without consuming a receipt, and replay rejection across different valid signatures. Expired request timestamps remain explicit failures. Still **offline-only**; no production credential vault, audit trail or live HTTP endpoint.

## Isolated HTTP contract fixture (2026-11-23)

Added `fastapi_fixture.py` and `test_fastapi_fixture.py` (nine HTTP TestClient scenarios), plus pinned FastAPI/httpx dependencies in the dedicated offline CI workflow. The fixture has its own synthetic credential, ephemeral SQLite database and `/offline-fixture/intake` route. It is **not imported into the production backend**, has no production authorization/membership store, and must not be deployed or publicly exposed. Real deployment requires an authenticated tenant registry, provider-specific signature verification, a reviewed migration and threat-model/security review. HTTP status tests do not imply production readiness.
