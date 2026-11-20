'use strict';
// Synthetic cross-PR contract verification. Requires checkout of landing PR #32
// and lead-triage PR #31. Never calls real email, Meta or production systems.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const net = require('node:net');
const { spawn, spawnSync } = require('node:child_process');

const landing = path.resolve(process.env.CORE8_LANDING_DIR || '');
const triage = path.resolve(process.env.CORE8_TRIAGE_DIR || '');
const phpScript = path.join(landing, 'apps/landing/server/lead.php');
const triageScript = path.join(triage, 'apps/lead-triage-pilot/lib/intake.cjs');
const serverScript = path.join(triage, 'apps/lead-triage-pilot/server.cjs');
const secret = 'synthetic-contract-secret-not-for-production';
const origin = 'https://contract.example.invalid';
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const readJson = (s) => { try { return JSON.parse(s); } catch { return null; } };

function request(port, pathname, body, headers = {}) {
  const raw = typeof body === 'string' ? body : JSON.stringify(body);
  return new Promise((resolve, reject) => {
    const req = http.request({
      host: '127.0.0.1', port, path: pathname, method: 'POST',
      headers: { 'Content-Type': 'application/json', Origin: origin, 'Content-Length': Buffer.byteLength(raw), ...headers }
    }, (res) => {
      let data = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => resolve({ status: res.statusCode, json: readJson(data) }));
    });
    req.on('error', reject);
    req.end(raw);
  });
}

async function freePort() {
  const s = net.createServer();
  await new Promise((resolve, reject) => s.once('error', reject).listen(0, '127.0.0.1', resolve));
  const port = s.address().port;
  await new Promise((resolve) => s.close(resolve));
  return port;
}

async function run() {
  assert.ok(process.env.CORE8_LANDING_DIR && process.env.CORE8_TRIAGE_DIR, 'Set both checkout directories');
  for (const p of [phpScript, triageScript, serverScript]) assert.ok(fs.existsSync(p), 'Missing ' + p);
  const check = spawnSync('php', ['-v'], { encoding: 'utf8' });
  assert.equal(check.status, 0, 'PHP executable is required');
  const modules = spawnSync('php', ['-m'], { encoding: 'utf8' });
  assert.match(modules.stdout, /^mbstring$/mi, 'PHP mbstring extension required');

  const { parseLeadEmail } = require(triageScript);
  const { createApp } = require(serverScript);
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'core8-synthetic-contract-'));
  const spool = path.join(temp, 'spool');
  const db = path.join(temp, 'local-pilot');
  fs.mkdirSync(spool);
  const config = {
    to: 'leads@example.invalid', from: 'Core8-AI <sender@example.invalid>',
    secret, allowed_origins: [origin], consent_text_ids: ['he-v1', 'en-v1'],
    spool_dir: spool, rate_limit_dir: path.join(temp, 'rate-limits')
  };
  const configPath = path.join(temp, 'config.php');
  fs.writeFileSync(configPath, "<?php return json_decode(base64_decode('" +
    Buffer.from(JSON.stringify(config), 'utf8').toString('base64') + "'), true);");
  const phpPort = await freePort();
  const php = spawn('php', ['-S', '127.0.0.1:' + phpPort, '-t', landing + '/apps/landing'], {
    env: { ...process.env, CORE8_LEAD_CONFIG: configPath },
    stdio: 'ignore'
  });
  let app;
  try {
    let ready = false;
    for (let n = 0; n < 60; n++) {
      if (php.exitCode !== null) throw new Error('PHP exited before ready');
      try {
        const r = await request(phpPort, '/server/lead.php', '{}', { Origin: 'https://blocked.example.invalid' });
        if (r.status === 403) { ready = true; break; }
      } catch {}
      await sleep(100);
    }
    assert.ok(ready, 'PHP test handler did not start');

    const he = {
      name: 'לקוח בדיקה', company: 'עסק הדגמה', email: 'person@example.invalid',
      phone: '', message: 'מבקש הדגמת שירות', lang: 'he', consent: true,
      consent_text_id: 'he-v1', website: ''
    };
    const en = {
      ...he, name: 'Sample Person', company: 'Synthetic Business',
      message: 'Please arrange a demo.', lang: 'en', consent_text_id: 'en-v1'
    };

    const first = await request(phpPort, '/server/lead.php', he);
    assert.equal(first.status, 202, 'HE form must accept synthetic lead');
    const second = await request(phpPort, '/server/lead.php', en);
    assert.equal(second.status, 202, 'EN form must accept synthetic lead');
    assert.equal((await request(phpPort, '/server/lead.php', { ...he, consent: false })).status, 422);
    assert.equal((await request(phpPort, '/server/lead.php', { ...he, consent_text_id: 'unknown' })).status, 409);
    assert.equal((await request(phpPort, '/server/lead.php', he, { Origin: 'https://other.example.invalid' })).status, 403);
    assert.equal(fs.readdirSync(spool).length, 2, 'Only consented submissions are spooled');

    const bodies = fs.readdirSync(spool).map((file) => fs.readFileSync(path.join(spool, file), 'utf8'))
      .map((raw) => raw.slice(raw.indexOf('\n\n') + 2));
    const parsed = bodies.map((body) => parseLeadEmail(body, { secret }));
    assert.ok(parsed.every((p) => p.ok && p.verified === 'verified'), 'All leads must have valid HMAC');
    assert.deepEqual(parsed.map((p) => p.lead.lang).sort(), ['en', 'he']);
    assert.ok(parsed.every((p) => p.lead.consent.given));
    assert.equal(new Set(parsed.map((p) => p.lead.submissionId)).size, 2, 'Every submission has unique ID');

    const forged = bodies[0].replace(/sig: [0-9a-f]{64}/, 'sig: ' + '0'.repeat(64));
    assert.equal(parseLeadEmail(forged, { secret }).ok, false, 'Forged signature rejected');
    assert.equal(parseLeadEmail(bodies[0], { secret: 'wrong-signing-key' }).ok, false, 'Wrong key rejected');
    const unsigned = bodies[0].replace(/sig: [0-9a-f]{64}/, 'sig: none');
    assert.equal(parseLeadEmail(unsigned, { secret }).ok, false, 'Unsigned lead rejected with secret configured');

    app = createApp({ dataDir: db, leadSecret: secret, quiet: true });
    const apiPort = await app.listen(0);
    const localHeaders = { Origin: 'http://127.0.0.1:' + apiPort };
    const one = await request(apiPort, '/api/intake/email', { raw: bodies[0] }, localHeaders);
    assert.equal(one.status, 201, 'Synthetic verified lead created');
    const replay = await request(apiPort, '/api/intake/email', { raw: bodies[0] }, localHeaders);
    assert.equal(replay.status, 200, 'Duplicate returns success without new record');
    assert.equal(replay.json.duplicate, true);
    assert.equal((await request(apiPort, '/api/intake/email', { raw: forged }, localHeaders)).status, 422);
    assert.equal((await request(apiPort, '/api/intake/email', { raw: bodies[1] }, localHeaders)).status, 201);
    assert.equal(app.store.leads().length, 2, 'Only two synthetic leads saved');
    assert.ok(app.store.leads().every((l) => l.status === 'needs_review'), 'No approval or sending');
    assert.ok(app.store.verify().ok, 'Audit chain stays valid');

    process.stdout.write('PASS: real PHP spool -> signed HE/EN email -> Node parser -> local lead state; consent, tampering, replay, audit and review gate.\n');
  } finally {
    if (app) await app.close().catch(() => {});
    php.kill('SIGTERM');
    fs.rmSync(temp, { recursive: true, force: true });
  }
}

run().catch((err) => { console.error('FAIL:', err.message); process.exitCode = 1; });
