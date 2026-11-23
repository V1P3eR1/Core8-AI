# Core8-AI lead interoperability — delivery plan

**Scope:** lead-triage intake → canonical lead → deduplication → human review → approved downstream handoff.  
**Repository:** V1P3eR1/Core8-AI, draft PR #85.  
**Safety:** no production merge, deployment, customer data, credential changes, real messaging, bookings or payments without explicit approval.

## Work packages

| ID | Deliverable | Dependency | Acceptance / exit gate | State |
| --- | --- | --- | --- | --- |
| P0 | Canonical lead schema and offline validator | none | Node tests, browser parity and tenant mismatch regression pass | Implemented in draft; CI passed on earlier commit |
| P1 | Lead Triage offline preview adapter | P0 | unsigned/verified inputs, invalid consent, immutable input tests | Implemented in draft; consent behavior needs reconciliation |
| P2 | Hebrew RTL browser sandbox | P0 | no network, no storage, no unsafe DOM API; four synthetic scenarios | Implemented in draft |
| P3 | Review state machine | P0 | reviewer, source, consent and tenant gates; no simulated sending | Implemented in draft |
| P4 | Tenant-scoped dedup preview | P0 | duplicate and cross-tenant collision tests | Implemented in draft |
| P5 | PostgreSQL idempotency design | P4 | unique key and transaction/retry acceptance criteria | Design only; no migration executed |
| P6 | Actual PostgreSQL integration in isolated test environment | P5 | concurrent inserts, crash rollback, retry and conflict tests on real DB | Not started |
| P7 | Authenticated tenant-aware API | P6 | server-derived tenant identity, negative auth/RLS tests, audit and rate limiting | Not started |
| P8 | Approved outbox handoff | P7 | explicit human approval, idempotent delivery, audit, no unauthorized sends | Not started |
| P9 | Cross-module integration and pilot | P8 | receptionist/social adapters, consent provenance, operator UAT, privacy review | Not started |
| P10 | Production readiness | P9 | security review, observability, backups, rollback, owner sign-off | Not started |

## Immediate implementation sequence

1. **P1 correctness:** reject malformed consent in the adapter rather than silently converting to false; add regression.
2. **P0 robustness:** extend malformed-input tests, ensure validator does not throw for unexpected shapes.
3. **P5 verification:** add SQL contract tests that statically verify uniqueness and transactional design; this is *not* a substitute for real DB tests.
4. **P6 preparation:** inspect current FastAPI/PostgreSQL schema and migrations before creating a compatible, isolated test-only implementation.
5. **P6 execution:** run PostgreSQL concurrency tests in CI or an isolated environment; only after schema compatibility is established.
6. **P7–P10:** implement sequentially with independent review and explicit authorization for external/production effects.

## Required integration decisions

- Confirm target backend and migration framework after code inspection; do not assume the draft contract maps to main.
- Define canonical payload hash and source-signature trust boundary.
- Define authoritative tenant resolver, database RLS and allowed service roles.
- Define contact consent provenance and retention/erasure rules.
- Define real downstream systems and human-approval ownership.

## Verification and reporting

Each increment: commit to draft branch → GitHub Actions checks → fix failures → update this plan and Notion project registry. Report **implemented**, **tested**, **proposed**, and **not started** separately. A passing secret scan does not establish full security. Do not merge or deploy automatically.
