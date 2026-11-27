'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { validateEnvelope } = require('./validate.cjs');
const fixture = () => ({
  schema_version: 'core8.lead.v1',
  tenant_id: 'trusted-tenant-A',
  lead_id: 'synthetic-lead-001',
  source: { system: 'receptionist_demo', source_submission_id: 'fake-001', verified: false },
  received_at: '2026-11-23T00:00:00Z',
  language: 'he',
  contact: { name: 'Fictional Person', email: null, phone: null, company: null },
  inquiry: { message: 'Synthetic inquiry', intent: 'unknown', service: null },
  consent: { given: false, text_id: null, recorded_at: null },
  workflow: { state: 'needs_review', human_approved: false },
  simulation: true
});
const check = (x, opts = {}) => validateEnvelope(x, { expectedTenantId: 'trusted-tenant-A', ...opts });
test('synthetic receptionist envelope is valid for offline-only use', () => assert.deepEqual(check(fixture()), {ok:true,errors:[]}));
test('cross-tenant injection fails closed', () => {const x=fixture();x.tenant_id='trusted-tenant-B';assert.ok(check(x).errors.includes('tenant_mismatch'));});
test('missing trusted tenant context fails closed', () => assert.ok(validateEnvelope(fixture()).errors.includes('tenant_mismatch')));
test('invalid contact format is rejected', () => {const x=fixture();x.contact.email='bad@';assert.ok(check(x).errors.includes('invalid_contact'));});
test('simulated leads cannot be marked sent', () => {const x=fixture();x.workflow.state='sent';x.workflow.human_approved=true;assert.ok(check(x).errors.includes('simulated_sent_forbidden'));});
test('production requires explicit gate even when otherwise complete', () => {
 const x=fixture();x.simulation=false;x.source.verified=true;x.consent.given=true;x.contact.email='fictional@example.test';
 assert.ok(check(x).errors.includes('production_not_allowed'));
 assert.equal(check(x,{allowProduction:true}).ok,true);
});
test('production rejects missing consent or unverified source', () => {
 const x=fixture();x.simulation=false;x.contact.email='fictional@example.test';
 assert.ok(check(x,{allowProduction:true}).errors.includes('production_without_consent'));
 assert.ok(check(x,{allowProduction:true}).errors.includes('production_unverified_source'));
});
test('production requires a contact channel', () => {
 const x=fixture();x.simulation=false;x.consent.given=true;x.source.verified=true;
 assert.ok(check(x,{allowProduction:true}).errors.includes('production_without_contact_channel'));
});
test('sent status always requires human approval', () => {
 const x=fixture();x.simulation=false;x.consent.given=true;x.source.verified=true;x.contact.email='fictional@example.test';x.workflow.state='sent';
 assert.ok(check(x,{allowProduction:true}).errors.includes('sent_without_human_approval'));
});
test('non-object payload rejected without exception', () => assert.deepEqual(check(null),{ok:false,errors:['invalid_envelope']}));
