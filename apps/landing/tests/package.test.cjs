'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { build, launchProblems, prerender, SITE_FILES } = require('../tools/package.cjs');
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
  // An unfinished copy: endpoint and consent version empty, legal pages with placeholders.
  const src = tmp();
  copyTree(src);
  const edit = (f, fn) => fs.writeFileSync(path.join(src, f), fn(fs.readFileSync(path.join(src, f), 'utf8')));
  edit('content.js', (s) => s.replace(/formEndpoint: '[^']*'/, "formEndpoint: ''").replace(/consentTextId: '[^']*'/, "consentTextId: ''"));
  for (const f of ['privacy.html', 'accessibility.html']) edit(f, (s) => s.replace('</main>', '<p>[להשלים]</p></main>'));
  const out = tmp();
  const r = build({ root: src, out: path.join(out, 'site'), launch: true });
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
  edit('content.js', (s) => s.replace(/formEndpoint: '[^']*'/, "formEndpoint: 'server/lead.php'").replace(/consentTextId: '[^']*'/, "consentTextId: 'v1'"));
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
  assert.match(fs.readFileSync(path.join(out, 'index.html'), 'utf8'), /<h1 data-i18n="hero\.title">[^<]+<\/h1>/);
});

test('built index.html carries the Hebrew text without JavaScript, for crawlers and link previews', () => {
  const out = tmp();
  build({ out });
  const html = fs.readFileSync(path.join(out, 'index.html'), 'utf8');
  assert.match(html, /<title>Core8-AI — פחות עבודה חוזרת\. יותר זמן לעסק שלך\.<\/title>/);
  assert.match(html, /<h1 data-i18n="hero\.title">פחות עבודה חוזרת\. יותר זמן לעסק שלך\.<\/h1>/);
  assert.match(html, /<meta name="description" content="אנחנו ממפים תהליכים[^"]+" data-i18n-content="meta\.description">/);
  assert.match(html, /<meta property="og:title" content="Core8-AI — [^"]+"/);
  assert.match(html, /<meta property="og:description" content="אנחנו ממפים[^"]+"/);
  assert.equal((html.match(/data-i18n="[^"]+"><\//g) || []).length, 0, 'no element is left without text');
  assert.match(html, /<html lang="he" dir="rtl">/);
  // Text is escaped, and unknown keys stop the build instead of shipping blanks.
  assert.equal(prerender('<p data-i18n="k"></p>', { k: '<b>&"', 'meta.title': 't' }), '<p data-i18n="k">&lt;b&gt;&amp;&quot;</p>');
  assert.throws(() => prerender('<p data-i18n="nope"></p>', { 'meta.title': 't' }), /unknown text keys: nope/);
});

test('the committed page is ready to launch', () => {
  assert.deepEqual(launchProblems(ROOT), []);
});

test('VPS build: no PHP handler is shipped, and --noindex keeps the search-engine block', () => {
  const out = tmp();
  const r = build({ out, launch: true, staticOnly: true, noindex: true });
  assert.equal(r.ok, true);
  assert.ok(!fs.existsSync(path.join(out, 'server')), 'no server folder at all');
  assert.ok(r.files.every((f) => !f.startsWith('server/')));
  for (const f of ['index.html', 'privacy.html', 'accessibility.html']) {
    const html = fs.readFileSync(path.join(out, f), 'utf8');
    assert.match(html, /name="robots" content="noindex, nofollow"/, f + ' stays out of search engines');
    assert.ok(!/class="draft"/.test(html), f + ' has no draft banner');
  }
  const indexable = tmp();
  build({ out: indexable, launch: true, staticOnly: true });
  assert.ok(!/noindex/.test(fs.readFileSync(path.join(indexable, 'index.html'), 'utf8')));
});
