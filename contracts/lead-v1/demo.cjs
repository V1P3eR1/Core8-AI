'use strict';
/**
 * Read-only, synthetic interoperability demonstration.
 * Run: node contracts/lead-v1/demo.cjs
 * No network, disk writes, credentials, real contacts or customer systems.
 */
const { previewPilotLead } = require('./preview-pilot.cjs');
const { validateEnvelope } = require('./validate.cjs');

function runDemo() {
  const parsed = {
    ok: true, verified: 'unsigned',
    lead: {
      submissionId: '0123456789abcdef',
      submittedAt: '2026-11-23T00:00:00.000Z',
      form: 'contact',
      lang: 'he',
      contact: { name: 'Fictional Demo Customer', company: 'Example Clinic', email: 'demo@example.test', phone: null },
      message: 'Synthetic appointment inquiry', consent: { given: true, textId: 'demo-consent-v1' }
    }
  };
  const trustedContext = { tenantId: 'demo-tenant-01', leadId: 'demo-lead-01' };
  const preview = previewPilotLead(parsed, trustedContext);
  if (!preview.ok) throw new Error('Demo adapter rejected fixture: ' + preview.errors.join(','));
  const validation = validateEnvelope(preview.envelope, { expectedTenantId: trustedContext.tenantId });
  if (!validation.ok) throw new Error('Demo contract rejected fixture: ' + validation.errors.join(','));
  const crossTenant = validateEnvelope(preview.envelope, { expectedTenantId: 'different-tenant' });
  if (crossTenant.ok || !crossTenant.errors.includes('tenant_mismatch')) throw new Error('Cross-tenant negative gate did not reject');
  return {
    scenario: 'synthetic-lead-triage-to-canonical',
    adapter: 'PASS',
    contract: 'PASS',
    cross_tenant_rejected: true,
    simulated_only: preview.envelope.simulation,
    approved: preview.envelope.workflow.human_approved,
    status: preview.envelope.workflow.state,
    source_verified: preview.envelope.source.verified,
    side_effects: 'NONE'
  };
}
if (require.main === module) process.stdout.write(JSON.stringify(runDemo(), null, 2) + '\n');
module.exports = { runDemo };
