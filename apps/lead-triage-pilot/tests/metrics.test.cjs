'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { openStore } = require('../lib/store.cjs');
const { computeMetrics, evidenceReport, median } = require('../lib/metrics.cjs');
const { tmpDir } = require('./helpers.cjs');

function build() {
  let now = new Date('2026-11-20T08:00:00Z');
  const s = openStore(tmpDir(), { clock: () => now });
  const at = (iso) => { now = new Date(iso); };
  const tri = (cat, extra) => Object.assign({ engine: 'rules', model: null, category: cat, urgency: 'normal', language: 'en', draft: 'SECRET-DRAFT', flags: [], fallbackReason: null }, extra);
  // L-0001: received 07:30, added 08:00, drafted +2s, approved as-is +10m, sent +12m
  at('2026-11-20T08:00:00Z'); s.append('lead_added', 'L-0001', { text: 'SECRET-TEXT one', channel: 'email', receivedAt: '2026-11-20T07:30:00.000Z', label: 'SECRET-LABEL' });
  at('2026-11-20T08:00:02Z'); s.append('triage_completed', 'L-0001', tri('pricing'));
  at('2026-11-20T08:10:02Z'); s.append('decision_recorded', 'L-0001', { action: 'approve', finalText: 'SECRET-FINAL', reason: null });
  at('2026-11-20T08:12:00Z'); s.append('marked_sent', 'L-0001', { by: 'human' });
  // L-0002: drafted +4s, approved after edit +20m, not sent
  at('2026-11-20T09:00:00Z'); s.append('lead_added', 'L-0002', { text: 'SECRET-TEXT two', channel: 'whatsapp', receivedAt: null, label: null });
  at('2026-11-20T09:00:04Z'); s.append('triage_completed', 'L-0002', tri('demo_request', { engine: 'anthropic', model: 'm', flags: ['contains_link'] }));
  at('2026-11-20T09:20:04Z'); s.append('decision_recorded', 'L-0002', { action: 'edit', finalText: 'SECRET-FINAL', reason: null });
  // L-0003: model fell back, rejected +30m
  at('2026-11-20T10:00:00Z'); s.append('lead_added', 'L-0003', { text: 'SECRET-TEXT three', channel: 'email', receivedAt: null, label: null });
  at('2026-11-20T10:00:06Z'); s.append('triage_completed', 'L-0003', tri('other', { fallbackReason: 'model API returned HTTP 529' }));
  at('2026-11-20T10:30:06Z'); s.append('decision_recorded', 'L-0003', { action: 'reject', finalText: null, reason: 'SECRET-REASON' });
  // L-0004: waiting
  at('2026-11-20T11:00:00Z'); s.append('lead_added', 'L-0004', { text: 'SECRET-TEXT four', channel: 'email', receivedAt: null, label: null });
  at('2026-11-20T11:00:08Z'); s.append('triage_completed', 'L-0004', tri('pricing'));
  return s;
}

test('median handles empty, odd and even lists', () => {
  assert.equal(median([]), null);
  assert.equal(median([5, 1, 3]), 3);
  assert.equal(median([4, 1, 3, 2]), 2.5);
});

test('metrics are computed from the log', () => {
  const m = computeMetrics(build().leads());
  assert.equal(m.leads, 4);
  assert.equal(m.triaged, 4);
  assert.equal(m.awaitingReview, 1);
  assert.equal(m.decided, 3);
  assert.equal(m.approvedAsIs, 1);
  assert.equal(m.approvedAfterEdit, 1);
  assert.equal(m.rejected, 1);
  assert.equal(m.markedSent, 1);
  assert.equal(m.approvedAsIsShare, 0.333);
  assert.equal(m.medianDraftSeconds, 5);        // 2, 4, 6, 8
  assert.equal(m.medianReviewMinutes, 20);      // 10, 20, 30
  assert.equal(m.medianReceivedToSentMinutes, 42); // 07:30 -> 08:12
  assert.deepEqual(m.byCategory, { pricing: 2, demo_request: 1, other: 1 });
  assert.deepEqual(m.byEngine, { rules: 3, anthropic: 1 });
  assert.deepEqual(m.byChannel, { email: 3, whatsapp: 1 });
  assert.equal(m.modelFallbacks, 1);
  assert.equal(m.draftsFlagged, 1);
});

test('empty pilot reports nulls, not zeros or NaN', () => {
  const m = computeMetrics([]);
  assert.equal(m.leads, 0);
  assert.equal(m.approvedAsIsShare, null);
  assert.equal(m.medianReviewMinutes, null);
  assert.equal(m.medianReceivedToSentMinutes, null);
});

test('evidence report carries metrics, integrity and hashes but no text, drafts, labels or reasons', () => {
  const s = build();
  const report = evidenceReport(s, { engine: 'rules', model: null }, new Date('2026-11-21T00:00:00Z'));
  const json = JSON.stringify(report);
  assert.ok(!/SECRET/.test(json), 'no personal or free-text content leaks into the report');
  assert.equal(report.integrity.ok, true);
  assert.equal(report.events.length, 12);
  assert.equal(report.events[11].hash, report.integrity.head);
  assert.equal(report.metrics.leads, 4);
  assert.match(report.setup.sending, /cannot send/);
  assert.deepEqual(report.events[1].detail, { engine: 'rules', category: 'pricing', urgency: 'normal', fallback: false });
});
