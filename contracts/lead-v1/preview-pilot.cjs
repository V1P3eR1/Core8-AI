'use strict';
const { validateEnvelope } = require('./validate.cjs');

/** Pure preview adapter for parsed CORE8 LEAD v1 email.
 * Inputs are parsed results from the existing pilot's parseLeadEmail().
 * Tenant and canonical lead ID MUST come from trusted caller context.
 * Always produces simulation=true; never persists, sends or books.
 */
function previewPilotLead(parsed, context) {
  if (!parsed || parsed.ok !== true || !parsed.lead || !context ||
      typeof context.tenantId !== 'string' || !context.tenantId.trim() ||
      typeof context.leadId !== 'string' || !context.leadId.trim()) {
    return { ok: false, errors: ['invalid_input_or_trusted_context'] };
  }
  const p = parsed.lead;
  if (!p.contact || typeof p.contact !== 'object' || Array.isArray(p.contact) ||
      typeof p.consent !== 'object' || p.consent === null ||
      p.consent.given !== true) {
    return { ok: false, errors: ['invalid_pilot_lead'] };
  }
  const envelope = {
    schema_version: 'core8.lead.v1',
    tenant_id: context.tenantId,
    lead_id: context.leadId,
    source: {
      system: 'lead_triage',
      source_submission_id: p.submissionId,
      verified: parsed.verified === 'verified'
    },
    received_at: p.submittedAt,
    language: p.lang,
    contact: {
      name: p.contact.name,
      email: p.contact.email ?? null,
      phone: p.contact.phone ?? null,
      company: p.contact.company ?? null
    },
    inquiry: { message: p.message ?? '', intent: 'unknown', service: null },
    consent: { given: true, text_id: p.consent.textId ?? null, recorded_at: null },
    workflow: { state: 'needs_review', human_approved: false },
    simulation: true
  };
  const result = validateEnvelope(envelope, { expectedTenantId: context.tenantId });
  return result.ok ? { ok: true, envelope } : { ok: false, errors: result.errors };
}

module.exports = { previewPilotLead };
