'use strict';
/*
 * Tests for server/lead.php using PHP's built-in web server and the handler's
 * spool (dry-run) mode. No mail is sent. Skipped when `php` is not installed.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');
const { spawn, spawnSync } = require('node:child_process');

const ROOT = path.resolve(__dirname, '..');
const HAS_PHP = spawnSync('php', ['-v']).status === 0;
const SECRET = 'handler-test-secret-not-real';
const ORIGIN = 'https://landing.example.invalid';

function request(port, opts) {
  return new Promise((resolve, reject) => {
    const body = opts.rawBody !== undefined ? opts.rawBody : JSON.stringify(opts.body || {});
    const req = http.request({ host: '127.0.0.1', port, path: '/server/lead.php', method: opts.method || 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json', Origin: ORIGIN, 'Content-Length': Buffer.byteLength(body) }, opts.headers || {}) }, (res) => {
      let data = ''; res.on('data', (c) => { data += c; });
      res.on('end', () => { let json = null; try { json = JSON.parse(data); } catch (e) { /* not JSON */ } resolve({ status: res.statusCode, json, text: data }); });
    });
    req.on('error', reject); req.end(body);
  });
}

async function start(configure) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'core8-handler-'));
  const spool = path.join(dir, 'spool'); fs.mkdirSync(spool);
  const cfg = Object.assign({ to: 'leads@example.invalid', from: 'Core8-AI website <no-reply@example.invalid>', secret: SECRET,
    allowed_origins: [ORIGIN], consent_text_ids: ['he-v1', 'en-v1'], spool_dir: spool, rate_limit_dir: dir }, configure || {});
  const cfgFile = path.join(dir, 'cfg.php');
  if (configure !== null) fs.writeFileSync(cfgFile, '<?php return json_decode(' + JSON.stringify(JSON.stringify(cfg)) + ', true);');
  const port = 20000 + Math.floor(Math.random() * 20000);
  const php = spawn('php', ['-S', '127.0.0.1:' + port, '-t', ROOT], { env: Object.assign({}, process.env, { CORE8_LEAD_CONFIG: cfgFile }), stdio: 'ignore' });
  for (let i = 0; i < 50; i++) {
    try { await request(port, { method: 'GET' }); break; } catch (e) { await new Promise((r) => setTimeout(r, 100)); }
  }
  return { port, spool, files: () => fs.readdirSync(spool).map((f) => fs.readFileSync(path.join(spool, f), 'utf8')), stop: () => { php.kill(); fs.rmSync(dir, { recursive: true, force: true }); } };
}

function decode(mail) {
  const m = /-----BEGIN CORE8 LEAD v1-----\n([\s\S]+?)-----END CORE8 LEAD v1-----\nsig: ([0-9a-f]{64})/.exec(mail);
  assert.ok(m, 'lead block present');
  const b64 = m[1].replace(/\s/g, '');
  assert.equal(m[2], crypto.createHmac('sha256', SECRET).update(b64).digest('hex'), 'signature verifies');
  return JSON.parse(Buffer.from(b64, 'base64url').toString('utf8'));
}

const good = () => ({ name: 'דנה לדוגמה', company: 'חברה לדוגמה', email: 'dana@example.invalid', phone: '', message: 'מעוניינים בשיחת אפיון', website: '', consent: true, consent_text_id: 'he-v1', lang: 'he' });
const opt = { skip: HAS_PHP ? false : 'php is not installed' };

test('valid submission is accepted and produces one signed CORE8 LEAD v1 message', opt, async () => {
  const s = await start();
  try {
    const r = await request(s.port, { body: good() });
    assert.equal(r.status, 202);
    assert.deepEqual(r.json, { ok: true });
    const mails = s.files();
    assert.equal(mails.length, 1);
    const [head, ...rest] = mails[0].split('\n\n');
    assert.match(head, /^To: leads@example\.invalid\nSubject: \[CORE8-LEAD\] v1\n/);
    assert.ok(/^[\x00-\x7f]*$/.test(mails[0]), 'whole message is ASCII');
    assert.ok(!mails[0].includes('dana@') && !mails[0].includes('דנה'), 'no visitor data outside the encoded block');
    const p = decode(rest.join('\n\n'));
    assert.equal(p.v, 1);
    assert.match(p.id, /^[0-9a-f]{16}$/);
    assert.ok(Math.abs(new Date(p.submitted_at) - Date.now()) < 60000);
    assert.deepEqual([p.name, p.company, p.email, p.message, p.consent, p.consent_text_id, p.lang, p.form],
      ['דנה לדוגמה', 'חברה לדוגמה', 'dana@example.invalid', 'מעוניינים בשיחת אפיון', true, 'he-v1', 'he', 'landing']);
    if (process.env.WRITE_FIXTURE) fs.writeFileSync(process.env.WRITE_FIXTURE, rest.join('\n\n'));
  } finally { s.stop(); }
});

test('visitor input can never reach a mail header', opt, async () => {
  const s = await start();
  try {
    const evil = Object.assign(good(), { name: 'Dana\r\nBcc: victim@example.invalid\r\nSubject: hacked', message: 'x\r\n\r\nFrom: someone' });
    assert.equal((await request(s.port, { body: evil })).status, 202);
    const head = s.files()[0].split('\n\n')[0];
    assert.ok(!/Bcc|victim|hacked/i.test(head), head);
    assert.equal(head.split('\n').length, 7, 'exactly the fixed headers');
  } finally { s.stop(); }
});

test('refuses bad origin, method, content type, JSON, oversize and unknown consent text', opt, async () => {
  const s = await start();
  try {
    assert.equal((await request(s.port, { body: good(), headers: { Origin: 'https://evil.example.invalid' } })).status, 403);
    assert.equal((await request(s.port, { method: 'GET' })).status, 405);
    assert.equal((await request(s.port, { rawBody: 'name=x', headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })).status, 415);
    assert.equal((await request(s.port, { rawBody: '{nope' })).status, 400);
    assert.equal((await request(s.port, { body: Object.assign(good(), { message: 'x'.repeat(20000) }) })).status, 413);
    assert.equal((await request(s.port, { body: Object.assign(good(), { consent_text_id: 'made-up' }) })).status, 409);
    assert.equal(s.files().length, 0, 'nothing was sent');
  } finally { s.stop(); }
});

test('validation: name, contact and consent', opt, async () => {
  const s = await start();
  try {
    const bad = async (patch, error) => { const r = await request(s.port, { body: Object.assign(good(), patch) }); assert.equal(r.status, 422, JSON.stringify(patch)); assert.equal(r.json.error, error); };
    await bad({ name: '   ' }, 'name');
    await bad({ email: 'nope' }, 'contact');
    await bad({ email: '', phone: '' }, 'contact');
    await bad({ consent: false }, 'consent');
    assert.equal(s.files().length, 0);
  } finally { s.stop(); }
});

test('honeypot looks like success but sends nothing; rate limit stops the sixth submission', opt, async () => {
  const s = await start();
  try {
    assert.equal((await request(s.port, { body: Object.assign(good(), { website: 'http://spam.example.invalid' }) })).status, 202);
    assert.equal(s.files().length, 0);
    for (let i = 0; i < 5; i++) assert.equal((await request(s.port, { body: Object.assign(good(), { email: '', phone: '+972 50 000 000' + i }) })).status, 202);
    const sixth = await request(s.port, { body: good() });
    assert.equal(sixth.status, 429);
    assert.equal(s.files().length, 5);
  } finally { s.stop(); }
});

test('answers 503 until it is configured', opt, async () => {
  const s = await start(null);
  try { assert.equal((await request(s.port, { body: good() })).status, 503); } finally { s.stop(); }
  const t = await start({ secret: '' });
  try { assert.equal((await request(t.port, { body: good() })).status, 503); } finally { t.stop(); }
});
