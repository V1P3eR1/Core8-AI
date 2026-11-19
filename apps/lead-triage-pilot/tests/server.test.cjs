'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createApp } = require('../server.cjs');
const { tmpDir, raw } = require('./helpers.cjs');

async function start(triage) {
  const app = createApp({ dataDir: tmpDir(), triage, quiet: true });
  const port = await app.listen(0);
  const post = (p, body, headers) => raw(port, { method: 'POST', path: p, body, headers });
  const get = (p, headers) => raw(port, { path: p, headers });
  return { app, port, post, get };
}

test('full review cycle: add, draft, approve after edit, mark sent', async () => {
  const { app, post, get } = await start();
  const added = await post('/api/leads', { text: 'Hi, how much does an agent cost?', channel: 'email', receivedAt: '2026-01-01T10:00:00Z', label: 'Acme' });
  assert.equal(added.status, 201);
  const lead = added.json.lead;
  assert.equal(lead.id, 'L-0001');
  assert.equal(lead.status, 'needs_review');
  assert.equal(lead.triage.category, 'pricing');
  assert.equal(lead.triage.engine, 'rules');

  const untouched = await post('/api/leads/L-0001/decision', { action: 'approve', finalText: lead.triage.draft });
  assert.equal(untouched.status, 400, 'template placeholder must be filled before approval');
  assert.match(untouched.json.error, /placeholder/);
  assert.equal((await post('/api/leads/L-0001/sent', {})).status, 409, 'cannot mark sent before approval');

  const ok = await post('/api/leads/L-0001/decision', { action: 'approve', finalText: 'Hello Dana, could we set up a short call?' });
  assert.equal(ok.status, 200);
  assert.equal(ok.json.lead.decision.action, 'edit', 'server decides that the draft was edited');
  assert.equal(ok.json.lead.status, 'approved');
  assert.equal((await post('/api/leads/L-0001/decision', { action: 'reject', reason: 'x' })).status, 409, 'one decision per lead');
  assert.equal((await post('/api/leads/L-0001/retriage', {})).status, 409);

  const sent = await post('/api/leads/L-0001/sent', {});
  assert.equal(sent.json.lead.status, 'sent');
  assert.equal((await post('/api/leads/L-0001/sent', {})).status, 409);

  const state = (await get('/api/state')).json;
  assert.equal(state.integrity.ok, true);
  assert.equal(state.integrity.events, 4);
  assert.equal(state.metrics.approvedAfterEdit, 1);
  assert.equal(state.config.engine, 'rules');
  assert.deepEqual(app.store.events().map((e) => e.type), ['lead_added', 'triage_completed', 'decision_recorded', 'marked_sent']);
  await app.close();
});

test('approving a model draft unchanged counts as approved-as-drafted; reject needs a reason', async () => {
  const fetchImpl = async () => ({ ok: true, json: async () => ({ content: [{ type: 'text', text: JSON.stringify({ category: 'demo_request', urgency: 'normal', language: 'en', draft: 'Hello, which day suits you for a short call?', rationale: 'r' }) }] }) });
  const { app, post } = await start({ engine: 'anthropic', apiKey: 'test-key-not-real', model: 'test-model', fetchImpl });
  const a = (await post('/api/leads', { text: 'Can we meet?' })).json.lead;
  assert.equal(a.triage.engine, 'anthropic');
  assert.equal(a.channel, 'other', 'unknown channel defaults to other');
  const d = await post('/api/leads/L-0001/decision', { action: 'approve', finalText: a.triage.draft });
  assert.equal(d.json.lead.decision.action, 'approve');

  await post('/api/leads', { text: 'Another inquiry about a demo' });
  assert.equal((await post('/api/leads/L-0002/decision', { action: 'reject', reason: '  ' })).status, 400);
  assert.equal((await post('/api/leads/L-0002/decision', { action: 'approve', finalText: '' })).status, 400);
  assert.equal((await post('/api/leads/L-0002/decision', { action: 'send' })).status, 400);
  const again = await post('/api/leads/L-0002/retriage', {});
  assert.equal(again.json.lead.triageCount, 2);
  const r = await post('/api/leads/L-0002/decision', { action: 'reject', reason: 'Not relevant' });
  assert.equal(r.json.lead.status, 'rejected');
  assert.ok(!JSON.stringify(app.store.events()).includes('test-key-not-real'), 'API key never reaches the log');
  await app.close();
});

test('input validation', async () => {
  const { app, post, port } = await start();
  assert.equal((await post('/api/leads', { text: ' ' })).status, 400);
  assert.equal((await post('/api/leads', { text: 'hello there', receivedAt: 'yesterday' })).status, 400);
  assert.equal((await post('/api/leads', { text: 'hello there', receivedAt: '2999-01-01T00:00:00Z' })).status, 400);
  assert.equal((await post('/api/leads/L-9999/decision', { action: 'approve', finalText: 'x' })).status, 404);
  assert.equal((await raw(port, { method: 'POST', path: '/api/leads', rawBody: '{nope', headers: { 'Content-Type': 'application/json' } })).status, 400);
  assert.equal((await raw(port, { method: 'POST', path: '/api/leads', rawBody: 'text=hi', headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })).status, 415);
  assert.equal((await post('/api/leads', { text: 'x'.repeat(70 * 1024) })).status, 413);
  assert.equal((await post('/api/unknown', {})).status, 404);
  assert.equal(app.store.events().length, 0, 'nothing invalid was written');
  await app.close();
});

test('refuses foreign hosts, origins and cross-site requests', async () => {
  const { app, port, get, post } = await start();
  assert.equal((await get('/api/state', { Host: 'evil.example' })).status, 403);
  assert.equal((await get('/api/state', { Host: 'evil.example:' + port })).status, 403);
  assert.equal((await post('/api/leads', { text: 'hello there' }, { Origin: 'http://evil.example' })).status, 403);
  assert.equal((await post('/api/leads', { text: 'hello there' }, { 'Sec-Fetch-Site': 'cross-site' })).status, 403);
  assert.equal((await post('/api/leads', { text: 'hello there' }, { Origin: 'http://127.0.0.1:' + port, 'Sec-Fetch-Site': 'same-origin' })).status, 201);
  assert.equal((await get('/api/state', { Host: 'localhost:' + port })).status, 200);
  assert.equal(app.server.address().address, '127.0.0.1');
  await app.close();
});

test('static files: served with a strict CSP, no path traversal, GET only', async () => {
  const { app, get, port } = await start();
  const page = await get('/');
  assert.equal(page.status, 200);
  assert.match(page.headers['content-security-policy'], /default-src 'none'/);
  assert.match(page.headers['content-security-policy'], /connect-src 'self'/);
  assert.ok(!/unsafe-inline|unsafe-eval/.test(page.headers['content-security-policy']));
  assert.match(page.text, /DRAFTS ONLY/);
  assert.equal((await get('/app.js')).status, 200);
  assert.equal((await get('/styles.css')).status, 200);
  for (const p of ['/../server.cjs', '/%2e%2e/server.cjs', '/..%2fpackage.json', '/nope.html', '/app.js.map']) {
    assert.equal((await get(p)).status, 404, p);
  }
  assert.equal((await raw(port, { method: 'DELETE', path: '/' })).status, 405);
  await app.close();
});

test('report endpoint is redacted', async () => {
  const { app, post, get } = await start();
  await post('/api/leads', { text: 'CONFIDENTIAL inquiry about pricing from Dana', label: 'CONFIDENTIAL label' });
  const report = await get('/api/report');
  assert.equal(report.status, 200);
  assert.ok(!/CONFIDENTIAL|Dana/.test(report.text));
  assert.equal(report.json.metrics.leads, 1);
  assert.equal(report.json.integrity.ok, true);
  await app.close();
});

test('source has no sending capability and only one outbound URL', () => {
  const root = path.resolve(__dirname, '..');
  const files = ['server.cjs', 'lib/store.cjs', 'lib/triage.cjs', 'lib/metrics.cjs', 'lib/intake.cjs', 'lib/slots.cjs', 'public/app.js', 'public/index.html', 'public/styles.css'];
  const src = Object.fromEntries(files.map((f) => [f, fs.readFileSync(path.join(root, f), 'utf8')]));
  const urls = [];
  for (const [f, text] of Object.entries(src)) for (const m of text.matchAll(/https?:\/\/[^\s'"<>)]+/g)) urls.push(f + ' ' + m[0]);
  const external = urls.filter((u) => !/http:\/\/(127\.0\.0\.1|localhost)\b/.test(u) && !u.includes("'http://' + h"));
  assert.deepEqual(external, ['lib/triage.cjs https://api.anthropic.com/v1/messages']);
  const all = Object.values(src).join('\n');
  for (const re of [/nodemailer|smtp|sendmail|twilio|whatsapp\.com|graph\.facebook|gmail\.googleapis/i, /child_process|\beval\s*\(|new Function\b/, /innerHTML|document\.write|localStorage|sessionStorage|document\.cookie/]) {
    assert.ok(!re.test(all), String(re));
  }
  assert.ok(!/sk-ant-|AKIA[0-9A-Z]{16}/.test(all), 'no credential-shaped strings');
  assert.equal((all.match(/fetchImpl\(/g) || []).length, 1, 'exactly one outbound call site');
});
