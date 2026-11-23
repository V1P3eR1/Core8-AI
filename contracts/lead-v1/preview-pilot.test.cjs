'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { previewPilotLead } = require('./preview-pilot.cjs');

const parsed = () => ({
  ok: true, verified: 'unsigned',
  lead: {
    submissionId: 'abcdef0123456789', submittedAt: '2026-11-23T00:00:00.000Z',
    form: 'contact', lang: 'he',
    contact: { name: 'Synthetic Lead', company: 'Example Co', email: 'test@example.test', phone: null },
    message: 'Synthetic interest', consent: { given: true, textId: 'v1' }
  }
});
const ctx = () => ({ tenantId: 'trusted-tenant-A', leadId: 'trusted-lead-1' });
test('maps unsigned pilot lead to an isolated simulation with no approval', () => {
  const r = previewPilotLead(parsed(), ctx());
  assert.equal(r.ok, true);
  assert.equal(r.envelope.simulation, true);
  assert.equal(r.envelope.source.verified, false);
  assert.equal(r.envelope.tenant_id, 'trusted-tenant-A');
  assert.equal(r.envelope.workflow.human_approved, false);
  assert.equal(r.envelope.contact.email, 'test@example.test');
});
test('verified source maps to verified flag without changing simulation', () => {
  const p = parsed();p.verified = 'verified';
  const r = previewPilotLead(p, ctx());
  assert.equal(r.ok, true);assert.equal(r.envelope.source.verified, true);
  assert.equal(r.envelope.simulation, true);
});
test('rejects missing trusted tenant and canonical ID', () => {
  assert.equal(previewPilotLead(parsed(), {}).ok, false);
  assert.equal(previewPilotLead(parsed(), {tenantId:'A'}).ok, false);
});
test('ignores hostile tenant and lead IDs supplied by payload', () => {
  const p=parsed();p.lead.tenant_id='hostile-tenant';p.lead.lead_id='hostile-id';
  const r=previewPilotLead(p,ctx());assert.equal(r.ok,true);
  assert.equal(r.envelope.tenant_id,'trusted-tenant-A');
  assert.equal(r.envelope.lead_id,'trusted-lead-1');
});
test('rejects failed parse and malformed contact', () => {
  assert.equal(previewPilotLead({ok:false},ctx()).ok,false);
  const p=parsed();p.lead.contact=null;
  assert.equal(previewPilotLead(p,ctx()).ok,false);
});
test('does not mutate source record', () => {
  const p=parsed();const before=JSON.stringify(p);
  previewPilotLead(p,ctx());assert.equal(JSON.stringify(p),before);
});
test('invalid consent is rejected by canonical validator', () => {
  const p=parsed();p.lead.consent.given='yes';
  const r=previewPilotLead(p,ctx());
  assert.equal(r.ok,true);assert.equal(r.envelope.consent.given,false);
  assert.equal(r.envelope.simulation,true);
});
