'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.resolve(__dirname, '..');
const C = require('../content.js');
const read = (f) => fs.readFileSync(path.join(ROOT, f), 'utf8');
const FILES = ['index.html', 'styles.css', 'app.js', 'content.js'];

test('Hebrew and English copy have the same keys, none empty', () => {
  const he = Object.keys(C.strings.he).sort();
  assert.deepEqual(Object.keys(C.strings.en).sort(), he);
  for (const l of ['he', 'en']) for (const k of he) assert.ok(C.strings[l][k].trim(), `${l}.${k}`);
});

test('every data-i18n key in the page exists', () => {
  const html = read('index.html');
  const keys = [...html.matchAll(/data-i18n(?:-content)?="([^"]+)"/g)].map((m) => m[1]);
  assert.ok(keys.length > 60);
  for (const k of keys) assert.ok(k in C.strings.he, k);
});

test('copy follows the content rules: no figures, prices, 24/7, guarantees or result claims', () => {
  for (const l of ['he', 'en']) {
    for (const [k, v] of Object.entries(C.strings[l])) {
      const text = v.replace(/Core8-AI/g, '');
      assert.ok(!/\d/.test(text), `${l}.${k} contains a figure: ${v}`);
      assert.ok(!/[%₪$€]/.test(text), `${l}.${k} contains a price or percentage sign`);
      assert.ok(!/guarantee|never miss|autopilot|fully autonomous|around the clock|מובטח|מבטיחים לך|ללא הפסקה|אוטונומי לחלוטין|מסביב לשעון/i.test(text), `${l}.${k} makes a banned claim`);
    }
  }
});

test('page is static: no remote URLs, no network or storage APIs, strict CSP, not indexed', () => {
  for (const f of FILES) {
    const src = read(f);
    assert.ok(!/https?:\/\//i.test(src), f + ' has a remote URL');
    for (const re of [/\bfetch\s*\(/, /XMLHttpRequest/, /sendBeacon/, /WebSocket/, /localStorage|sessionStorage|document\.cookie/, /innerHTML|document\.write|\beval\s*\(/]) {
      assert.ok(!re.test(src), `${f} ${re}`);
    }
  }
  const html = read('index.html');
  assert.match(html, /default-src 'none'/);
  assert.match(html, /connect-src 'none'/);
  assert.match(html, /form-action 'none'/);
  assert.match(html, /name="robots" content="noindex, nofollow"/);
  assert.ok(!/unsafe-inline|unsafe-eval/.test(html));
  assert.ok(!/<form[^>]*action=/i.test(html), 'form has no action');
  assert.ok(!/etx|oia/i.test(html + read('content.js')), 'no third-party platform credit');
});

test('no contact details or credentials are committed; form endpoint is unset', () => {
  const all = FILES.map(read).join('\n');
  assert.ok(!/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/.test(all), 'no email address');
  assert.ok(!/\+?\d[\d\s().-]{7,}\d/.test(read('content.js') + read('index.html').replace(/content="[^"]*"/g, '')), 'no phone number');
  assert.ok(!/sk-ant-|AKIA[0-9A-Z]{16}|api[_-]?key\s*[:=]/i.test(all));
  assert.equal(C.config.formEndpoint, '');
});

test('text colours meet WCAG AA', () => {
  const css = read('styles.css');
  const v = (n) => new RegExp(`--${n}:\\s*(#[0-9a-fA-F]{6})`).exec(css)[1];
  const lum = (h) => { const c = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255).map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4)); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  for (const [fg, bg] of [['fg', 'bg'], ['fg', 'raise'], ['muted', 'bg'], ['muted', 'raise'], ['muted', 'sunken'], ['ink', 'primary'], ['warn-ink', 'warn'], ['primary', 'bg'], ['primary', 'sunken'], ['bad', 'raise'], ['ok', 'sunken']]) {
    assert.ok(ratio(v(fg), v(bg)) >= 4.5, `${fg} on ${bg} = ${ratio(v(fg), v(bg)).toFixed(2)}`);
  }
});
