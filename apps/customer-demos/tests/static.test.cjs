'use strict';
/*
 * Static guarantees for the offline demos: no network-capable code, no remote
 * URLs, no storage, no HTML injection sinks, no secret- or contact-shaped data.
 * These scans read source text; the browser smoke test checks runtime behaviour.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const DEMO = path.resolve(__dirname, '..', 'receptionist');
const files = fs.readdirSync(DEMO).filter((f) => fs.statSync(path.join(DEMO, f)).isFile());
const read = (f) => fs.readFileSync(path.join(DEMO, f), 'utf8');
const lineOf = (src, idx) => src.slice(0, idx).split('\n').length;

function scan(pattern, describe, only) {
  const hits = [];
  for (const f of files) {
    if (only && !only.test(f)) continue;
    const src = read(f);
    const re = new RegExp(pattern.source, pattern.flags.includes('g') ? pattern.flags : pattern.flags + 'g');
    let m;
    while ((m = re.exec(src))) hits.push(`${f}:${lineOf(src, m.index)} ${describe}: ${m[0]}`);
  }
  return hits;
}

test('demo folder contains only the expected static files', () => {
  assert.deepEqual(files.sort(), ['app.js', 'engine.js', 'fixtures.js', 'i18n.js', 'index.html', 'styles.css']);
});

test('no remote URLs or protocol-relative references', () => {
  assert.deepEqual(scan(/\b(?:https?|wss?|ftp):\/\/[^\s'"<>)]*/i, 'remote URL'), []);
  assert.deepEqual(scan(/(?:src|href|action)\s*=\s*["']\/\/[^"']*/i, 'protocol-relative URL'), []);
  assert.deepEqual(scan(/@import|\burl\(/, 'CSS external reference', /\.(css|html)$/), []);
});

test('no network, storage or dynamic-code APIs', () => {
  const banned = [
    /\bfetch\s*\(/, /XMLHttpRequest/, /\bWebSocket\b/, /\bEventSource\b/, /sendBeacon/,
    /\bimportScripts\b/, /\bimport\s*\(/, /serviceWorker/, /\bRTCPeerConnection\b/,
    /localStorage/, /sessionStorage/, /indexedDB/, /document\.cookie/,
    /\beval\s*\(/, /new\s+Function\b/, /innerHTML/, /outerHTML/, /insertAdjacentHTML/, /document\.write/,
    /window\.open/, /location\.(?:href|assign|replace)\s*[=(]/, /navigator\.(?:geolocation|clipboard|mediaDevices)/
  ];
  for (const re of banned) assert.deepEqual(scan(re, 'banned API'), [], String(re));
});

test('page loads only its own local scripts and stylesheet under a strict CSP', () => {
  const html = read('index.html');
  const scripts = [...html.matchAll(/<script\b[^>]*>/g)].map((m) => m[0]);
  assert.deepEqual(scripts, [
    '<script src="fixtures.js">', '<script src="i18n.js">', '<script src="engine.js">', '<script src="app.js">'
  ]);
  assert.deepEqual([...html.matchAll(/<link\b[^>]*>/g)].map((m) => m[0]), ['<link rel="stylesheet" href="styles.css">']);
  assert.ok(!/<(?:iframe|object|embed|img|video|audio|source|form[^>]*action)/i.test(html), 'no embedded remote-capable elements');
  assert.ok(!/\son[a-z]+\s*=/i.test(html), 'no inline event handlers');
  assert.ok(!/<style\b|style\s*=/i.test(html), 'no inline styles');
  const csp = /http-equiv="Content-Security-Policy"\s+content="([^"]+)"/.exec(html);
  assert.ok(csp, 'CSP meta tag present');
  for (const directive of ["default-src 'none'", "connect-src 'none'", "script-src 'self'", "style-src 'self'", "form-action 'none'", "base-uri 'none'"]) {
    assert.ok(csp[1].includes(directive), directive);
  }
  assert.ok(!/unsafe-inline|unsafe-eval|\*/.test(csp[1]), 'no unsafe CSP sources');
});

test('no credential-shaped strings', () => {
  const secrets = [
    /sk-[A-Za-z0-9_-]{16,}/, /AKIA[0-9A-Z]{16}/, /AIza[0-9A-Za-z_-]{20,}/, /gh[pousr]_[A-Za-z0-9]{20,}/,
    /xox[abprs]-[A-Za-z0-9-]{10,}/, /-----BEGIN [A-Z ]*PRIVATE KEY-----/, /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/,
    /\b(?:api[_-]?key|secret|password|passwd|access[_-]?token|bearer)\b\s*[:=]/i
  ];
  for (const re of secrets) assert.deepEqual(scan(re, 'secret-shaped'), [], String(re));
});

test('only reserved, non-routable sample contact data', () => {
  const emails = scan(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/, 'email').filter((h) => !/@example\.invalid$/.test(h));
  assert.deepEqual(emails, [], 'every email uses the reserved example.invalid domain');
  // Phone-like digit runs (7+ digits, optional separators). Hex colours are excluded.
  const phones = scan(/(?<![#\w.])\+?\d[\d\s().-]{7,}\d(?![\w])/, 'phone-like');
  assert.deepEqual(phones, []);
});

test('simulation wording is present in both languages and no outcome claims are made', () => {
  const i18n = require('../receptionist/i18n.js');
  assert.match(i18n.STRINGS.en['ui.banner'], /DEMO \/ SIMULATION/);
  assert.match(i18n.STRINGS.en['ui.banner'], /no messages sent/);
  assert.match(i18n.STRINGS.en['ui.banner'], /no bookings created/);
  assert.match(i18n.STRINGS.he['ui.banner'], /הדגמה \/ סימולציה/);
  assert.match(i18n.STRINGS.he['ui.banner'], /לא נשלחות הודעות/);
  assert.match(i18n.STRINGS.he['ui.banner'], /לא נקבעים תורים/);
  const all = Object.values(i18n.STRINGS.en).join('\n');
  // No ungrounded ROI / uptime / performance figures in customer-facing copy.
  assert.ok(!/\d+\s?%|\bROI\b|uptime|24\/7|guarantee/i.test(all), 'no KPI or guarantee claims');
  assert.ok(!/\b(?:booked|confirmed your appointment|message sent|we sent)\b/i.test(
    all.replace(/Nothing was booked/g, '')), 'no success claims');
});

test('text colours meet WCAG AA contrast on their backgrounds', () => {
  const css = read('styles.css');
  const v = (name) => new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`).exec(css)[1];
  const lum = (hex) => {
    const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const pairs = [
    ['fg', 'bg'], ['fg', 'bg-raise'], ['fg', 'bg-sunken'], ['fg', 'user'],
    ['fg-muted', 'bg'], ['fg-muted', 'bg-raise'], ['fg-muted', 'bg-sunken'],
    ['primary-ink', 'primary'], ['sim-ink', 'sim'], ['sim', 'bg-raise'], ['ok', 'bg-raise'], ['primary', 'bg']
  ];
  for (const [fg, bg] of pairs) {
    const r = ratio(v(fg), v(bg));
    assert.ok(r >= 4.5, `${fg} on ${bg} = ${r.toFixed(2)}:1`);
  }
});
