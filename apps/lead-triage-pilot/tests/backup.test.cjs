'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { tmpDir } = require('./helpers.cjs');
const { openStore } = require('../lib/store.cjs');
const { createBackup, restoreBackup } = require('../tools/secure-backup.cjs');

function fixture() {
  const parent = tmpDir(), dir = path.join(parent, 'source');
  const backup = path.join(parent, 'backup.enc');
  const restored = path.join(parent, 'restored');
  const keyFile = path.join(parent, 'backup.key');
  fs.writeFileSync(keyFile, crypto.randomBytes(48), { mode: 0o600 });
  const store = openStore(dir);
  store.append('lead_added', 'L-0001', {
    text: 'Only synthetic data', channel: 'website_form',
    submissionId: 'fixture-0001', contact: { email: 'fixture@example.invalid' },
    consent: { given: true, textId: 'he-v1' }
  });
  store.append('triage_completed', 'L-0001', {
    category: 'demo_request', language: 'he',
    draft: 'Synthetic draft', flags: [], urgency: 'normal'
  });
  fs.writeFileSync(path.join(dir, 'mailbox-state.json'),
    JSON.stringify({ uidValidity: 5, lastUid: 99 }), { mode: 0o600 });
  fs.writeFileSync(path.join(dir, 'password.hash'), 'synthetic-hash-only', { mode: 0o600 });
  return { parent, dir, backup, restored, keyFile, store };
}

test('AES-GCM synthetic encrypted archive has no PII and restores exact audit and mailbox state', () => {
  const f = fixture();
  const originalHead = f.store.verify().head;
  const done = createBackup(f.dir, f.backup, f.keyFile);
  assert.equal(done.status, 'encrypted');
  assert.equal(done.fileCount, 3);
  const bytes = fs.readFileSync(f.backup, 'utf8');
  for (const sensitive of ['fixture@example.invalid', 'Only synthetic data', 'synthetic-hash-only']) {
    assert.ok(!bytes.includes(sensitive));
  }
  assert.equal(restoreBackup(f.backup, f.restored, f.keyFile).status, 'restored');
  const renewed = openStore(f.restored);
  assert.equal(renewed.verify().head, originalHead);
  assert.equal(renewed.hasSubmission('fixture-0001'), true);
  assert.equal(renewed.leads()[0].status, 'needs_review');
  assert.equal(fs.readFileSync(path.join(f.restored, 'password.hash'), 'utf8'), 'synthetic-hash-only');
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(f.restored, 'mailbox-state.json'), 'utf8')),
    { uidValidity: 5, lastUid: 99 });
  assert.equal(f.store.verify().head, originalHead, 'original data must be untouched');
});

test('wrong backup key and tampered ciphertext fail without creating the restore target', () => {
  const f = fixture();
  createBackup(f.dir, f.backup, f.keyFile);
  const otherKey = path.join(f.parent, 'other.key');
  fs.writeFileSync(otherKey, crypto.randomBytes(48), { mode: 0o600 });
  assert.throws(() => restoreBackup(f.backup, f.restored, otherKey));
  assert.equal(fs.existsSync(f.restored), false);
  const record = JSON.parse(fs.readFileSync(f.backup, 'utf8'));
  record.tag = Buffer.alloc(16).toString('base64');
  fs.writeFileSync(f.backup, JSON.stringify(record));
  assert.throws(() => restoreBackup(f.backup, f.restored, f.keyFile));
  assert.equal(fs.existsSync(f.restored), false);
});

test('backup and restore refuse destructive overwrites', () => {
  const f = fixture();
  createBackup(f.dir, f.backup, f.keyFile);
  assert.throws(() => createBackup(f.dir, f.backup, f.keyFile), /Refusing to overwrite/);
  fs.mkdirSync(f.restored);
  assert.throws(() => restoreBackup(f.backup, f.restored, f.keyFile), /already exists/);
});

test('broken event log and symlink sources cannot be backed up', () => {
  const f = fixture();
  fs.appendFileSync(f.store.file, 'not a valid log entry\n');
  assert.throws(() => createBackup(f.dir, f.backup, f.keyFile));
  assert.equal(fs.existsSync(f.backup), false);
  const f2 = fixture();
  fs.renameSync(path.join(f2.dir, 'password.hash'), path.join(f2.dir, 'real-password.hash'));
  fs.symlinkSync(path.join(f2.dir, 'real-password.hash'), path.join(f2.dir, 'password.hash'));
  assert.throws(() => createBackup(f2.dir, f2.backup, f2.keyFile), /safe regular file/);
});

test('key file requires owner-only permissions', { skip: process.platform === 'win32' }, () => {
  const f = fixture();
  fs.chmodSync(f.keyFile, 0o644);
  assert.throws(() => createBackup(f.dir, f.backup, f.keyFile), /owner-only/);
  assert.equal(fs.existsSync(f.backup), false);
});
