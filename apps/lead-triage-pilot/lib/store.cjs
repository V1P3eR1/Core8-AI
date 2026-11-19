'use strict';
/*
 * Append-only, hash-chained event log for the lead-triage pilot.
 *
 * Every action (lead added, draft produced, human decision, marked sent) is one
 * JSON line. Each line carries the SHA-256 of the previous line's hash plus its
 * own content, so any later edit, deletion or reordering is detectable with
 * verify(). Current state is derived by replaying the log; nothing is updated
 * in place.
 *
 * The log holds real inquiry text. It must live OUTSIDE any git working tree.
 */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const GENESIS = '0'.repeat(64);
const TYPES = ['lead_added', 'triage_completed', 'decision_recorded', 'marked_sent'];

function canonical(e) {
  return JSON.stringify([e.seq, e.at, e.type, e.leadId, e.data]);
}

function hashOf(prev, e) {
  return crypto.createHash('sha256').update(prev + '\n' + canonical(e)).digest('hex');
}

function insideGitRepo(dir) {
  let cur = path.resolve(dir);
  for (;;) {
    if (fs.existsSync(path.join(cur, '.git'))) return cur;
    const up = path.dirname(cur);
    if (up === cur) return null;
    cur = up;
  }
}

function openStore(dataDir, opts) {
  opts = opts || {};
  const clock = opts.clock || (() => new Date());
  const dir = path.resolve(dataDir);
  const repo = insideGitRepo(dir);
  if (repo) {
    throw new Error(
      'Refusing to store pilot data inside a git repository (' + repo + '). ' +
      'Inquiry text is personal data. Set CORE8_PILOT_DATA to a folder outside any repo.');
  }
  fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  const file = path.join(dir, 'events.jsonl');
  let events = [];
  if (fs.existsSync(file)) {
    events = fs.readFileSync(file, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
  }

  function verify() {
    let prev = GENESIS;
    for (let i = 0; i < events.length; i++) {
      const e = events[i];
      if (e.seq !== i + 1) return { ok: false, events: events.length, brokenAt: i + 1, reason: 'sequence gap' };
      if (e.prev !== prev) return { ok: false, events: events.length, brokenAt: e.seq, reason: 'previous-hash mismatch' };
      if (e.hash !== hashOf(prev, e)) return { ok: false, events: events.length, brokenAt: e.seq, reason: 'content hash mismatch' };
      prev = e.hash;
    }
    return { ok: true, events: events.length, head: prev };
  }

  const loaded = verify();
  if (!loaded.ok && !opts.allowBroken) {
    throw new Error('Event log failed integrity check at event ' + loaded.brokenAt + ' (' + loaded.reason + '). Not appending to it.');
  }

  function append(type, leadId, data) {
    if (!TYPES.includes(type)) throw new Error('Unknown event type: ' + type);
    const prev = events.length ? events[events.length - 1].hash : GENESIS;
    const e = { seq: events.length + 1, at: clock().toISOString(), type, leadId, data };
    e.prev = prev;
    e.hash = hashOf(prev, e);
    fs.appendFileSync(file, JSON.stringify(e) + '\n', { mode: 0o600 });
    events.push(e);
    return e;
  }

  function leads() {
    const byId = new Map();
    for (const e of events) {
      if (e.type === 'lead_added') {
        byId.set(e.leadId, {
          id: e.leadId, addedAt: e.at, receivedAt: e.data.receivedAt, channel: e.data.channel,
          label: e.data.label, text: e.data.text, status: 'new', triage: null, triageCount: 0,
          decision: null, sentAt: null
        });
        continue;
      }
      const lead = byId.get(e.leadId);
      if (!lead) continue;
      if (e.type === 'triage_completed') {
        lead.triage = Object.assign({ at: e.at }, e.data);
        lead.triageCount += 1;
        if (lead.status === 'new') lead.status = 'needs_review';
      } else if (e.type === 'decision_recorded') {
        lead.decision = Object.assign({ at: e.at }, e.data);
        lead.status = e.data.action === 'reject' ? 'rejected' : 'approved';
      } else if (e.type === 'marked_sent') {
        lead.sentAt = e.at;
        lead.status = 'sent';
      }
    }
    return [...byId.values()].sort((a, b) => (a.addedAt < b.addedAt ? 1 : -1));
  }

  return {
    dir, file, append, verify, leads,
    events: () => events.slice(),
    get: (id) => leads().find((l) => l.id === id) || null,
    nextLeadId: () => 'L-' + String(events.filter((e) => e.type === 'lead_added').length + 1).padStart(4, '0')
  };
}

module.exports = { openStore, insideGitRepo, GENESIS, TYPES };
