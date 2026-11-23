'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..', 'social-content');
const csv = fs.readFileSync(path.join(root, 'calendar.csv'), 'utf8');
const storyboard = fs.readFileSync(path.join(root, 'README.md'), 'utf8');
const rows = csv.trimEnd().split(/\r?\n/).map(line => line.split(','));
const expected = [
  'status', 'platform', 'account_placeholder', 'language', 'content_pillar',
  'draft_title', 'proposed_copy', 'asset_status', 'scheduled_at',
  'approval_status', 'publication_status'
];

test('two unpublished bilingual drafts with stable CSV schema', () => {
  assert.deepEqual(rows[0], expected);
  assert.equal(rows.length, 3, 'header plus exactly two drafts');
  assert.deepEqual(rows.slice(1).map(r => r[3]).sort(), ['en', 'he']);
  for (const row of rows.slice(1)) {
    assert.equal(row.length, expected.length, 'no unescaped CSV delimiters');
    assert.equal(row[0], 'DRAFT');
    assert.equal(row[2], 'ACCOUNT_NOT_CONNECTED');
    assert.equal(row[7], 'STORYBOARD_ONLY');
    assert.equal(row[8], 'TBD');
    assert.equal(row[9], 'NOT_APPROVED');
    assert.equal(row[10], 'NOT_PUBLISHED');
    assert.ok(row[5].trim() && row[6].trim());
    assert.doesNotMatch(row.join(' '), /https?:\/\/|@[a-z0-9.-]+\.[a-z]{2,}/i);
  }
});

test('storyboards are marked as proposals and do not claim production assets', () => {
  assert.match(storyboard, /DRAFT \/ SIMULATION ONLY/);
  assert.match(storyboard, /Five-panel portfolio carousel/);
  assert.match(storyboard, /Educational reel/);
  assert.match(storyboard, /visual not produced/);
  assert.match(storyboard, /No content has been published/);
});
