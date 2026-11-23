# Core8-AI lead interoperability contract — proposal v0.1

**Status:** DRAFT; design only. No migration, database schema change, production API, real customer data or cross-module integration is implemented here.

## Existing source inventory (read from actual PR branches, 2026-11-23)

| Component | Source | Current lead representation | Caution |
|---|---|---|---|
| Offline receptionist | [PR #26](https://github.com/V1P3eR1/Core8-AI/pull/26), `apps/customer-demos/receptionist/engine.js` | `leadId`, `recordStatus`, `storage`, `fictional`, `business`, `name`, `contact` (single string), `intent`, `service`, `requestedSlot`, booking/message/handoff statuses | Entirely in-memory simulation; never import a demo lead into CRM |
| Lead Triage Pilot | [PR #31](https://github.com/V1P3eR1/Core8-AI/pull/31), `apps/lead-triage-pilot/lib/intake.cjs` | Signed/unsigned CORE8 LEAD v1 email: `submissionId`, `submittedAt`, `form`, `lang`, `contact{name,company,email,phone}`, `message`, `consent` | Signed source and consent checks are separate; unsigned data must not be silently trusted |
| Pilot event store | PR #31, `lib/store.cjs` | `id`, `receivedAt`, `channel`, `label`, `text`, `status`, `contact`, `consent`, `source`, `verified`, `submissionId` | Append-only hash chain, real inquiry text outside Git |
| Social Manager | [PR #53](https://github.com/V1P3eR1/Core8-AI/pull/53) and [PR #81](https://github.com/V1P3eR1/Core8-AI/pull/81) | Social drafts/auth reviewed separately; no verified production lead ingestion contract | Do not infer Meta lead sync or tenant authorization |

## Proposed normalized envelope (not yet implemented)

```json
{
  "schema_version": "core8.lead.v1",
  "tenant_id": "TENANT_ASSIGNED_BY_TRUSTED_SERVER",
  "lead_id": "SERVER_ASSIGNED_OPAQUE_ID",
  "source": {"system": "lead_triage", "source_submission_id": "OPAQUE_SOURCE_ID", "verified": false},
  "received_at": "2026-11-23T00:00:00Z",
  "language": "he",
  "contact": {"name": "FICTIONAL NAME", "email": null, "phone": null, "company": null},
  "inquiry": {"message": "FICTIONAL MESSAGE", "intent": "unknown", "service": null},
  "consent": {"given": false, "text_id": null, "recorded_at": null},
  "workflow": {"state": "needs_review", "human_approved": false},
  "simulation": true
}
```

The JSON above is a **shape illustration**, not a valid lead ready for processing. A real intake requires verified tenant authorization, a valid contact channel, consent and a secure store. Source-provided tenant IDs must never be trusted.

## Invariants and adapter rules

1. The trusted server assigns tenant ID from authenticated context and independently enforces cross-tenant access. Never use a tenant ID supplied by email, a demo browser, social payload or LLM output.
2. The trusted server assigns the canonical lead ID. Retain source submission ID separately for deduplication scoped to tenant and source.
3. `simulation=true` means no CRM write, email, SMS, calendar booking, payment, outbound social post or production side effect. Never promote a demo lead automatically.
4. Ingestion must distinguish `verified`, `unsigned` and `unknown` source authenticity; absence of a signature is not evidence of verification.
5. Consent must be affirmative, traceable to source text/version and independently checked before any contact or processing beyond permitted triage.
6. Keep email and phone in separate validated fields; do not parse the receptionist demo's free-text `contact` into production data without review.
7. The status transition `needs_review -> approved -> sent` requires authenticated human approval and auditable action. A simulated confirmation never means an appointment was booked.
8. Minimize and encrypt personal data; define retention/deletion rules with legal review. Do not store live leads in GitHub, Notion or demo fixtures.
9. Adapter mappings must be versioned and tested; never mutate the pilot's append-only event log or bypass its integrity verification.
10. Social Manager may reference a canonical lead ID after explicit authorization; social publishing and lead ingestion remain separate permission scopes.

## Proposed adapter matrix and acceptance gates

| Adapter | Mapping | Release gate |
|---|---|---|
| Receptionist offline -> canonical | Map intent/service and hypothetical slot; force simulation=true; no contact export to live tenant | Negative test that no live write occurs |
| Lead Triage v1 email -> canonical | Map submission ID, timestamps, language, structured contact, consent, signature state | Signed/unsigned tests, duplicate delivery tests, tenant authorization |
| Social Manager -> canonical | **TBD** pending verified API and permission model | Admin-only operator tests and cross-tenant negative tests |
| Canonical -> CRM | **NOT IMPLEMENTED** | Approval, retention, audit, encryption and idempotency |

**Do not merge or deploy** this proposal without security and data-governance review. Owners and policy decisions remain TBD rather than guessed.
