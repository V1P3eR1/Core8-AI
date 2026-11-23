# Core8-AI lead contract — offline demo

Run from the repository root with Node.js 22:

```sh
node contracts/lead-v1/demo.cjs
node --test contracts/lead-v1/*.test.cjs
```

The CLI uses only fictional, hard-coded data. It demonstrates a parsed Lead Triage v1-style object being converted into a canonical `core8.lead.v1` envelope, then checks that the expected tenant passes while a different tenant is rejected. It reports status, not customer contact details.

**This is not a production integration:** no pilot parser is imported, no mail is fetched, no browser app is served, no CRM is updated, and no network or storage access occurs. The trusted tenant ID and lead ID are deliberately supplied by a test fixture, not inferred from the payload. Authorization must be implemented and verified in the server before production use.

Expected output fields: `adapter: PASS`, `contract: PASS`, `cross_tenant_rejected: true`, `simulated_only: true`, `approved: false`, `side_effects: NONE`.

Contract proposal: [LEAD_INTEROPERABILITY_CONTRACT_DRAFT.md](../../docs/LEAD_INTEROPERABILITY_CONTRACT_DRAFT.md).

## Simulation-only workflow review

`transition-preview.cjs` implements a **pure demonstration** of allowed status transitions. `needs_review -> approved` requires a fictional reviewer role, verified source, explicit consent, matching trusted tenant context and `simulationOnly: true`. Rejection and return to review are modeled, but `sent` is never a permitted transition. The function cannot authenticate a user and **must not** be wired to a production endpoint.

Run all regression tests:

```sh
node --test contracts/lead-v1/*.test.cjs
```

The browser UI uses the same structural validator as Node.js, but its scenario selection and synthetic context are not security controls. Actual tenant authorization, identity verification, consent audit and sending must be implemented on a trusted server with separate review.

## Tenant-scoped deduplication preview

`dedup-preview.cjs` provides a pure, offline duplicate check using the tuple `(trustedTenantId, sourceSystem, sourceSubmissionId)`. A duplicate within one tenant/source is detected; matching submission IDs across tenants or different sources remain distinct. Length-prefixed keys avoid separator collisions. This implementation deliberately stores nothing and does **not** provide concurrency safety, atomic uniqueness, idempotent API semantics, a database unique index, or a tenant authorization boundary. Those are required before live ingestion. Only trusted server context may supply the tenant ID; never use a source payload's claimed tenant as authority.
