'use strict';
/**
 * Pure offline deduplication preview. No storage, database or network.
 * A trusted caller MUST supply tenant identity; source IDs are untrusted input.
 */
function isToken(x) {
  return typeof x === 'string' && x.length > 0 && x.length <= 256 &&
    /^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(x);
}
function makeDedupKey({ tenantId, sourceSystem, sourceSubmissionId } = {}) {
  if (![tenantId, sourceSystem, sourceSubmissionId].every(isToken)) {
    return { ok: false, error: 'invalid_dedup_identity' };
  }
  // Length prefixes prevent delimiter collision; no PII is included.
  const parts = [tenantId, sourceSystem, sourceSubmissionId];
  return { ok: true, key: parts.map(s => s.length + ':' + s).join('|') };
}
function previewDedup(records, candidate, trustedTenantId) {
  if (!Array.isArray(records) || records.length > 1000 || !candidate ||
      !isToken(trustedTenantId) || candidate.tenant_id !== trustedTenantId) {
    return { ok: false, error: 'invalid_input_or_tenant' };
  }
  const id = makeDedupKey({
    tenantId: trustedTenantId,
    sourceSystem: candidate.source?.system,
    sourceSubmissionId: candidate.source?.source_submission_id
  });
  if (!id.ok) return { ok: false, error: id.error };
  for (const record of records) {
    if (!record || record.tenant_id !== trustedTenantId) continue;
    const existing = makeDedupKey({
      tenantId: trustedTenantId,
      sourceSystem: record.source?.system,
      sourceSubmissionId: record.source?.source_submission_id
    });
    if (existing.ok && existing.key === id.key) {
      return { ok: true, duplicate: true, existingLeadId: record.lead_id ?? null };
    }
  }
  return { ok: true, duplicate: false, existingLeadId: null };
}
module.exports = { makeDedupKey, previewDedup };
