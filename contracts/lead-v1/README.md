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
