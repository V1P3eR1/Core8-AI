'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { build, launchProblems, SITE_FILES } = require('../tools/package.cjs');
const ROOT = path.resolve(__dirname, '..');
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'core8-pkg-'));

function copyTree(dest) {
  for (const f of SITE_FILES.concat(['server/lead-config.example.php'])) {
    fs.mkdirSync(path.dirname(path.join(dest, f)), { recursive: true });
    fs.copyFileSync(path.join(ROOT, f), path.join(dest, f));
  }
}

test('preview build copies the site and keeps the draft banner and noindex', () => {
  const out = tmp();
  const r = build({ out });
  assert.equal(r.ok, true);
  for (const f of SITE_FILES) assert.ok(fs.existsSync(path.join(out, f)), f);
  const html = fs.readFileSync(path.join(out, 'index.html'), 'utf8');
  assert.match(html, /noindex, nofollow/);
  assert.match(html, /class="draft"/);
  assert.ok(!fs.existsSync(path.join(out, 'tests')), 'tests are not shipped');
  assert.ok(!fs.existsSync(path.join(out, 'server', 'lead-config.php')), 'no real config in the bundle');
  assert.ok(!fs.existsSync(path.join(out, 'server', 'lead-config.example.php')));
});

test('launch build is refused while the page is unfinished, and writes nothing', () => {
  const out = tmp();
  const r = build({ out: path.join(out, 'site'), launch: true });
  assert.equal(r.ok, false);
  assert.ok(r.problems.some((p) => /formEndpoint/.test(p)));
  assert.ok(r.problems.some((p) => /consentTextId/.test(p)));
  assert.ok(r.problems.some((p) => /privacy\.html/.test(p)));
  assert.ok(r.problems.some((p) => /accessibility\.html/.test(p)));
  assert.ok(!fs.existsSync(path.join(out, 'site')));
});

test('once everything is completed, the launch build strips the draft banner and noindex only', () => {
  const src = tmp();
  copyTree(src);
  const edit = (f, fn) => fs.writeFileSync(path.join(src, f), fn(fs.readFileSync(path.join(src, f), 'utf8')));
  edit('content.js', (s) => s.replace("formEndpoint: ''", "formEndpoint: 'server/lead.php'").replace("consentTextId: ''", "consentTextId: 'v1'"));
  for (const f of ['privacy.html', 'accessibility.html']) edit(f, (s) => s.replace(/\[[^\]]*\]/g, 'done'));
  assert.deepEqual(launchProblems(src), []);
  const out = path.join(src, 'out', 'site');
  const r = build({ root: src, out, launch: true });
  assert.equal(r.ok, true);
  for (const f of ['index.html', 'privacy.html', 'accessibility.html']) {
    const html = fs.readFileSync(path.join(out, f), 'utf8');
    assert.ok(!/noindex/.test(html), f + ' is indexable');
    assert.ok(!/class="draft"/.test(html), f + ' has no draft banner');
    assert.match(html, /Content-Security-Policy/);
    assert.match(html, /<title>/);
  }
  const before = fs.readFileSync(path.join(src, 'index.html'), 'utf8').split('\n').length;
  const after = fs.readFileSync(path.join(out, 'index.html'), 'utf8').split('\n').length;
  assert.equal(before - after, 3, 'exactly the comment, the robots tag and the banner were removed');
});
