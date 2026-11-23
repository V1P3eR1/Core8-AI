'use strict';
// Offline contract tests for the unpublished Core8-AI showcase package.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const dir = __dirname;
const read = (name) => fs.readFileSync(path.join(dir, name), 'utf8');
const html = read('index.html');
const csv = read('calendar.csv');
const readme = read('README.md');

test('exactly five bilingual, uniquely identified showcase panels', () => {
  const panels = [...html.matchAll(/<article\b[^>]*aria-labelledby="([^"]+)"/g)]
    .map((m) => m[1]);
  assert.deepEqual(panels, ['panel-0', 'panel-1', 'panel-2', 'panel-3', 'panel-4']);
  for (const id of panels) {
    assert.match(html, new RegExp('<h2 id="' + id + '">'));
  }
  assert.equal((html.match(/class="en"\s+lang="en"\s+dir="ltr"/g) || []).length, 5);
  assert.match(html, /<html lang="he" dir="rtl">/);
});

test('only local relative links, all resolve within the checkout', () => {
  const hrefs = [...html.matchAll(/<a\b[^>]*href="([^"]+)"/g)]
    .map((m) => m[1]);
  assert.equal(hrefs.length, 3);
  for (const href of hrefs) {
    assert.ok(!/^[a-z][\w+.-]*:|^\/\//i.test(href), 'non-local URI forbidden');
    const url = new URL(href, 'https://example.invalid/docs/customer-showcase/index.html');
    assert.equal(url.origin, 'https://example.invalid');
    const full = path.resolve(dir, decodeURIComponent(href.split('?')[0]));
    const repo = path.resolve(dir, '..', '..');
    assert.ok(full.startsWith(repo + path.sep), 'link must stay within repo');
    assert.ok(fs.statSync(full).isFile(), 'linked file must exist: ' + href);
  }
  assert.ok(hrefs.some((x) => x.includes('?lang=he')));
  assert.ok(hrefs.some((x) => x.includes('?lang=en')));
});

test('strictly offline HTML with no script, forms, trackers or remote assets', () => {
  assert.match(html, /Content-Security-Policy/);
  assert.match(html, /default-src 'none'/);
  for (const blocked of [
    /<script\b/i, /<iframe\b/i, /<form\b/i,
    /<img\b/i, /<link\b/i, /<video\b/i, /<audio\b/i,
    /\b(?:https?|wss?):\/\//i, /\bon[a-z]+\s*=/i,
    /\bfetch\s*\(/i, /XMLHttpRequest/i,
  ]) {
    assert.doesNotMatch(html, blocked);
  }
});

test('calendar contains exactly two unscheduled DRAFT items', () => {
  const rows = csv.trim().split(/\r?\n/).map((line) => line.split(','));
  assert.deepEqual(rows[0], ['id', 'asset', 'language', 'status', 'publish_at', 'approval']);
  assert.equal(rows.length, 3);
  const ids = new Set();
  for (const row of rows.slice(1)) {
    assert.equal(row.length, 6);
    assert.equal(row[3], 'DRAFT');
    assert.equal(row[4], '');
    assert.equal(row[5], 'pending');
    assert.ok(row[0].startsWith('CORE8-DEMO-'));
    assert.ok(!ids.has(row[0]));
    ids.add(row[0]);
  }
});

test('no live booking, social publication or completed-reel claims', () => {
  assert.match(html, /לא נשלחות הודעות/);
  assert.match(html, /לא נקבעים תורים/);
  assert.match(html, /Fictional examples only/);
  assert.match(readme, /not a rendered video/);
  assert.match(readme, /not calendar events/);
  assert.match(readme, /owner\s+approval remain outstanding/);
});
