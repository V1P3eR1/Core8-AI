'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { HE } = require('../public/i18n.js');
const pub = (f) => fs.readFileSync(path.join(__dirname, '..', 'public', f), 'utf8');

// Every English string the interface can show, collected from the sources.
function keys() {
  const found = new Set();
  for (const f of ['app.js', 'login.js']) {
    const js = pub(f);
    for (const m of js.matchAll(/\bt\('((?:[^'\\]|\\.)*)'/g)) found.add(m[1]);
    // label maps looked up through L(map, code): { code: 'English label', ... }
    for (const m of js.matchAll(/var (?:STATUS|CATEGORY|CHANNEL|FLAG|SOURCE|VERIFIED) = \{([\s\S]*?)\};/g)) {
      for (const v of m[1].matchAll(/: '((?:[^'\\]|\\.)*)'/g)) if (v[1]) found.add(v[1]);
    }
    for (const m of js.matchAll(/\[\['needs_review'[\s\S]*?\]\]/g)) for (const v of m[0].matchAll(/, '([^']+)'\]/g)) found.add(v[1]);
  }
  for (const f of ['index.html', 'login.html']) {
    const html = pub(f);
    for (const m of html.matchAll(/<[^>]*\bdata-i18n(?=[\s>])[^>]*>([^<]+)</g)) found.add(m[1].trim());
    for (const m of html.matchAll(/aria-label="([^"]+)" data-i18n-aria/g)) found.add(m[1]);
  }
  return [...found];
}

test('every interface string has a Hebrew translation', () => {
  const all = keys();
  assert.ok(all.length > 90, 'the scan found the interface strings (' + all.length + ')');
  assert.deepEqual(all.filter((k) => !Object.prototype.hasOwnProperty.call(HE, k)), []);
});

test('translations keep their placeholders and are really Hebrew', () => {
  const vars = (s) => (s.match(/\{\w+\}/g) || []).sort();
  for (const [en, he] of Object.entries(HE)) {
    assert.deepEqual(vars(he), vars(en), en);
    if (en !== 'WhatsApp') assert.match(he, /[֐-׿]/, en);
  }
});

test('user-facing server errors are translated', () => {
  const src = ['server.cjs', 'lib/intake.cjs'].map((f) => fs.readFileSync(path.join(__dirname, '..', f), 'utf8')).join('\n');
  const msgs = [];
  for (const m of src.matchAll(/(?:HttpError\(\d+, |error: |fail\()'((?:[^'\\]|\\.)*)'/g)) msgs.push(m[1]);
  assert.ok(msgs.length >= 20);
  // Protocol-level refusals the interface itself never triggers stay in English.
  const internal = ['Invalid JSON', 'Unknown decision', 'Content-Type must be application/json', 'Forbidden host',
    'Forbidden origin', 'Cross-site request refused', 'Not found', 'Method not allowed',
    // The public website form shows its own messages; the review interface never calls it.
    'Too many requests'];
  assert.deepEqual(msgs.filter((k) => !internal.includes(k) && !Object.prototype.hasOwnProperty.call(HE, k)), []);
});
