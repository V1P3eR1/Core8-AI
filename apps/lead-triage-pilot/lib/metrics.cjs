'use strict';
/*
 * Pilot metrics and the redacted evidence report.
 * Metrics are computed only from the event log. The report contains counts,
 * durations and hashes; it never contains inquiry text, drafts, labels or reasons.
 */
function median(nums) {
  if (!nums.length) return null;
  const s = nums.slice().sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}
const secs = (a, b) => (new Date(b) - new Date(a)) / 1000;
const round = (n, d) => (n === null ? null : Math.round(n * 10 ** d) / 10 ** d);
const share = (n, total) => (total ? round(n / total, 3) : null);

function computeMetrics(leads) {
  const triaged = leads.filter((l) => l.triage);
  const decided = leads.filter((l) => l.decision);
  const approvedAsIs = decided.filter((l) => l.decision.action === 'approve');
  const edited = decided.filter((l) => l.decision.action === 'edit');
  const rejected = decided.filter((l) => l.decision.action === 'reject');
  const sent = leads.filter((l) => l.sentAt);
  const count = (arr, key) => arr.reduce((acc, x) => { const k = key(x); acc[k] = (acc[k] || 0) + 1; return acc; }, {});
  const dates = leads.map((l) => l.addedAt).sort();
  return {
    leads: leads.length,
    triaged: triaged.length,
    awaitingReview: leads.filter((l) => l.status === 'needs_review').length,
    decided: decided.length,
    approvedAsIs: approvedAsIs.length,
    approvedAfterEdit: edited.length,
    rejected: rejected.length,
    markedSent: sent.length,
    approvedAsIsShare: share(approvedAsIs.length, decided.length),
    editedShare: share(edited.length, decided.length),
    rejectedShare: share(rejected.length, decided.length),
    medianDraftSeconds: round(median(triaged.map((l) => secs(l.addedAt, l.triage.at))), 1),
    medianReviewMinutes: round(median(decided.map((l) => secs(l.triage.at, l.decision.at) / 60)), 1),
    medianReceivedToSentMinutes: round(median(sent.filter((l) => l.receivedAt).map((l) => secs(l.receivedAt, l.sentAt) / 60).filter((m) => m >= 0)), 1),
    byCategory: count(triaged, (l) => l.triage.category),
    byEngine: count(triaged, (l) => l.triage.engine),
    byChannel: count(leads, (l) => l.channel),
    modelFallbacks: triaged.filter((l) => l.triage.fallbackReason).length,
    draftsFlagged: triaged.filter((l) => (l.triage.flags || []).some((f) => f !== 'has_placeholder_to_fill')).length,
    firstLeadAt: dates[0] || null,
    lastLeadAt: dates[dates.length - 1] || null
  };
}

function evidenceReport(store, config, now) {
  const leads = store.leads();
  return {
    title: 'Core8-AI lead-triage pilot - evidence report',
    generatedAt: now.toISOString(),
    notice: 'Redacted: counts, durations and hashes only. No inquiry text, drafts, names or contact details.',
    setup: {
      engine: config.engine, model: config.model,
      sending: 'none - the tool cannot send; a human copies approved text and sends it',
      storage: 'single local append-only file, SHA-256 hash chained'
    },
    integrity: store.verify(),
    metrics: computeMetrics(leads),
    events: store.events().map((e) => ({ seq: e.seq, at: e.at, type: e.type, leadId: e.leadId, hash: e.hash,
      detail: e.type === 'triage_completed' ? { engine: e.data.engine, category: e.data.category, urgency: e.data.urgency, fallback: !!e.data.fallbackReason }
        : e.type === 'decision_recorded' ? { action: e.data.action }
        : e.type === 'lead_added' ? { channel: e.data.channel } : {} }))
  };
}

module.exports = { computeMetrics, evidenceReport, median };
