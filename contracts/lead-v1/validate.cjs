'use strict';

/** Offline-only validation of a proposed canonical lead envelope.
 * Does not write, send, persist, or infer tenant identity.
 * Never treat this validator as an authentication or authorization boundary.
 */
const STATES = new Set(['needs_review', 'approved', 'sent', 'rejected']);
const SYSTEMS = new Set(['lead_triage', 'receptionist_demo', 'social']);
const isObject = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const isString = x => typeof x === 'string' && x.trim().length > 0;
const isTimestamp = x => typeof x === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(x) && !Number.isNaN(Date.parse(x));
const validEmail = x => x === null || (typeof x === 'string' && x.length <= 200 && /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(x));
const validPhone = x => x === null || (typeof x === 'string' && /^\+?[\d\s().-]{7,20}$/.test(x) && (x.match(/\d/g) || []).length >= 7);

function validateEnvelope(lead, { expectedTenantId, allowProduction = false } = {}) {
  const errors = [];
  const fail = (code) => errors.push(code);
  if (!isObject(lead)) return { ok: false, errors: ['invalid_envelope'] };
  if (lead.schema_version !== 'core8.lead.v1') fail('invalid_version');
  if (!isString(expectedTenantId) || lead.tenant_id !== expectedTenantId) fail('tenant_mismatch');
  if (!isString(lead.lead_id)) fail('missing_lead_id');
  if (!isObject(lead.source) || !SYSTEMS.has(lead.source.system) ||
      !isString(lead.source.source_submission_id) ||
      typeof lead.source.verified !== 'boolean') fail('invalid_source');
  if (!isTimestamp(lead.received_at)) fail('invalid_received_at');
  if (!['he', 'en'].includes(lead.language)) fail('invalid_language');
  if (!isObject(lead.contact) || !isString(lead.contact.name) ||
      !validEmail(lead.contact.email) || !validPhone(lead.contact.phone)) fail('invalid_contact');
  if (!isObject(lead.inquiry) || typeof lead.inquiry.message !== 'string' ||
      !isString(lead.inquiry.intent)) fail('invalid_inquiry');
  if (!isObject(lead.consent) || typeof lead.consent.given !== 'boolean') fail('invalid_consent');
  if (!isObject(lead.workflow) || !STATES.has(lead.workflow.state) ||
      typeof lead.workflow.human_approved !== 'boolean') fail('invalid_workflow');
  if (typeof lead.simulation !== 'boolean') fail('invalid_simulation');
  if (lead.simulation === false && !allowProduction) fail('production_not_allowed');
  if (lead.simulation === true && lead.workflow.state === 'sent') fail('simulated_sent_forbidden');
  if (lead.workflow?.state === 'sent' && lead.workflow.human_approved !== true) fail('sent_without_human_approval');
  if (lead.simulation === false && lead.consent?.given !== true) fail('production_without_consent');
  if (lead.simulation === false && lead.source?.verified !== true) fail('production_unverified_source');
  if (lead.simulation === false && !lead.contact?.email && !lead.contact?.phone) fail('production_without_contact_channel');
  return { ok: errors.length === 0, errors };
}

module.exports = { validateEnvelope };
