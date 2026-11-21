'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { openStore, insideGitRepo, GENESIS } = require('../lib/store.cjs');
const { tmpDir, steppingClock } = require('./helpers.cjs');

function seeded(dir) {
  const s = openStore(dir, { clock: steppingClock('2026-11-20T08:00:00Z', 60) });
  s.append('lead_added', 'L-0001', { text: 'Hello, can I get a demo?', channel: 'email', receivedAt: null, label: null });
  s.append('triage_completed', 'L-0001', { engine: 'rules', category: 'demo_request', urgency: 'normal', language: 'en', draft: 'Hi', flags: [], fallbackReason: null });
  s.append('decision_recorded', 'L-0001', { action: 'approve', finalText: 'Hi', reason: null });
  s.append('marked_sent', 'L-0001', { by: 'human' });
  return s;
}

test('events are appended as a hash chain and state is derived by replay', () => {
  const dir = tmpDir();
  const s = seeded(dir);
  const ev = s.events();
  assert.equal(ev.length, 4);
  assert.equal(ev[0].prev, GENESIS);
  for (let i = 1; i < ev.length; i++) assert.equal(ev[i].prev, ev[i - 1].hash);
  assert.deepEqual(s.verify(), { ok: true, events: 4, head: ev[3].hash });
  const lead = s.get('L-0001');
  assert.equal(lead.status, 'sent');
  assert.equal(lead.decision.action, 'approve');
  assert.equal(lead.sentAt, '2026-11-20T08:03:00.000Z');
});

test('log survives a restart and keeps the same head hash', () => {
  const dir = tmpDir();
  const head = seeded(dir).verify().head;
  const again = openStore(dir);
  assert.equal(again.verify().head, head);
  assert.equal(again.leads().length, 1);
  assert.equal(again.nextLeadId(), 'L-0002');
});

test('editing, deleting or reordering a line is detected and blocks further writes', () => {
  for (const tamper of [
    (lines) => { lines[1] = lines[1].replace('demo_request', 'pricing'); return lines; },
    (lines) => { lines.splice(2, 1); return lines; },
    (lines) => { [lines[1], lines[2]] = [lines[2], lines[1]]; return lines; }
  ]) {
    const dir = tmpDir();
    const s = seeded(dir);
    const lines = fs.readFileSync(s.file, 'utf8').trim().split('\n');
    fs.writeFileSync(s.file, tamper(lines).join('\n') + '\n');
    assert.throws(() => openStore(dir), /failed integrity check/);
    const broken = openStore(dir, { allowBroken: true }).verify();
    assert.equal(broken.ok, false);
    assert.ok(broken.brokenAt >= 2);
  }
});

test('refuses to keep data inside a git repository', () => {
  const repoRoot = path.resolve(__dirname, '..', '..', '..');
  assert.equal(insideGitRepo(__dirname), repoRoot);
  assert.throws(() => openStore(path.join(__dirname, 'pilot-data')), /Refusing to store pilot data inside a git repository/);
  assert.ok(!fs.existsSync(path.join(__dirname, 'pilot-data')), 'no folder was created');
});

test('unknown event types are rejected; data file is private to the user', () => {
  const dir = tmpDir();
  const s = seeded(dir);
  assert.throws(() => s.append('message_sent', 'L-0001', {}), /Unknown event type/);
  if (process.platform !== 'win32') assert.equal(fs.statSync(s.file).mode & 0o077, 0);
});
