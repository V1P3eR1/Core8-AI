'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..', 'social-content');
const csv = fs.readFileSync(path.join(root, 'calendar.csv'), 'utf8');
const storyboard = fs.readFileSync(path.join(root, 'README.md'), 'utf8');
// Parse RFC 4180-style quoted fields, commas and escaped quotes without a dependency.
function parseCsv(input) {
  const rows = [];
  let row = [], field = '', quoted = false;
  for (let i = 0; i < input.length; i++) {
    const ch = input[i];
    if (quoted) {
      if (ch === '"' && input[i + 1] === '"') { field += '"'; i++; }
      else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') {
      assert.equal(field, '', 'quote must begin a CSV field');
      quoted = true;
    } else if (ch === ',') {
      row.push(field); field = '';
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && input[i + 1] === '\n') i++;
      row.push(field); rows.push(row); row = []; field = '';
    } else {
      field += ch;
    }
  }
  assert.equal(quoted, false, 'unterminated quoted CSV field');
  if (row.length || field) { row.push(field); rows.push(row); }
  return rows;
}
const rows = parseCsv(csv);
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

test('CSV parser supports quoted commas, escaped quotes and embedded newlines', () => {
  assert.deepEqual(parseCsv('a,b\r\n"hello, world","say ""hi"""\r\n'), [
    ['a', 'b'], ['hello, world', 'say "hi"']
  ]);
  assert.deepEqual(parseCsv('a,b\n"line 1\nline 2",ok\n'), [
    ['a', 'b'], ['line 1\nline 2', 'ok']
  ]);
  assert.throws(() => parseCsv('a,"unclosed'), /unterminated/);
});
