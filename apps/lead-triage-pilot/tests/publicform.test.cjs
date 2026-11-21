'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { createApp } = require('../server.cjs');
const { hashPassword } = require('../lib/auth.cjs');
const F = require('../lib/publicform.cjs');
const { tmpDir, raw } = require('./helpers.cjs');

const SITE = 'core8-ai.example';
const GOOD = {
  name: 'Dana Levi', company: 'Levi Ltd', email: 'dana@example.com', phone: '', message: 'We want to automate our quotes.',
  website: '', consent: true, consent_text_id: 'he-v1', lang: 'he'
};

async function start(extra) {
  const app = createApp(Object.assign({
    dataDir: tmpDir(), quiet: true,
    auth: { publicHost: 'agent.example.com', passwordHash: hashPassword('correct horse battery') },
    formHosts: [SITE, 'www.' + SITE]
  }, extra || {}));
  const port = await app.listen(0);
  const form = (body, headers) => raw(port, {
    method: 'POST', path: '/api/public/lead', body,
    headers: Object.assign({ Host: SITE, Origin: 'https://' + SITE, 'X-Forwarded-For': '203.0.113.7' }, headers || {})
  });
  return { app, port, form };
}

test('validator: consent, versions, contact rules and honeypot', () => {
  assert.equal(F.validatePublicLead(GOOD).ok, true);
  assert.deepEqual(F.validatePublicLead(Object.assign({}, GOOD, { website: 'http://spam' })), { ok: true, honeypot: true });
  assert.equal(F.validatePublicLead(Object.assign({}, GOOD, { consent: 'yes' })).status, 400, 'consent must be the boolean true');
  assert.equal(F.validatePublicLead(Object.assign({}, GOOD, { consent_text_id: 'he-v0' })).status, 409);
  assert.equal(F.validatePublicLead(Object.assign({}, GOOD, { name: '   ' })).status, 400);
  assert.equal(F.validatePublicLead(Object.assign({}, GOOD, { email: '' })).status, 400, 'needs e-mail or phone');
  assert.equal(F.validatePublicLead(Object.assign({}, GOOD, { email: '', phone: '054-1234567' })).ok, true);
  assert.equal(F.validatePublicLead(Object.assign({}, GOOD, { email: 'not-an-email' })).status, 400);
  assert.equal(F.validatePublicLead(null).ok, false);
  assert.equal(F.validatePublicLead([1, 2]).ok, false);
  const long = F.validatePublicLead(Object.assign({}, GOOD, { message: 'x'.repeat(5000), name: 'n'.repeat(500) }));
  assert.equal(long.lead.message.length, 2000);
  assert.equal(long.lead.contact.name.length, 120);
});

test('a form submission becomes a lead for review, with contact, consent and a draft', async () => {
  const { app, port, form } = await start();
  const r = await form(GOOD);
  assert.equal(r.status, 202);
  assert.deepEqual(r.json, { ok: true }, 'nothing about the lead or the tool is echoed back');
  const lead = app.store.leads()[0];
  assert.equal(lead.source, 'form_direct');
  assert.equal(lead.channel, 'website_form');
  assert.equal(lead.status, 'needs_review');
  assert.deepEqual(lead.contact, { name: 'Dana Levi', company: 'Levi Ltd', email: 'dana@example.com', phone: null });
  assert.equal(lead.consent.textId, 'he-v1');
  assert.ok(lead.triage && lead.triage.draft, 'a draft was prepared');
  assert.equal(app.store.verify().ok, true);
  assert.equal((await raw(port, { path: '/api/state', headers: { Host: 'agent.example.com' } })).status, 401, 'the review side still needs a login');
  await app.close();
});

test('the form host reaches exactly one route; nothing else of the tool is exposed there', async () => {
  const { app, port } = await start();
  const H = { Host: SITE, Origin: 'https://' + SITE };
  for (const [method, p] of [['GET', '/'], ['GET', '/login.html'], ['GET', '/api/state'], ['POST', '/api/login'], ['POST', '/api/leads'],
    ['POST', '/api/intake/email'], ['GET', '/api/public/lead'], ['POST', '/api/public/lead/x'], ['GET', '/app.js']]) {
    const r = await raw(port, { method, path: p, headers: H, body: method === 'POST' ? {} : undefined });
    assert.equal(r.status, 404, method + ' ' + p);
  }
  const onAgentHost = await raw(port, { method: 'POST', path: '/api/public/lead', body: GOOD, headers: { Host: 'agent.example.com', Origin: 'https://agent.example.com' } });
  assert.equal(onAgentHost.status, 401, 'the public route does not exist on the tool host either');
  assert.equal(app.store.leads().length, 0);
  await app.close();
});

test('refuses foreign origins, wrong content types, big bodies and bad JSON', async () => {
  const { app, form } = await start();
  assert.equal((await form(GOOD, { Origin: 'https://evil.example' })).status, 403);
  assert.equal((await form(GOOD, { Origin: '' })).status, 403, 'no Origin header, no lead');
  assert.equal((await form(GOOD, { Origin: 'http://' + SITE })).status, 403, 'https only');
  assert.equal((await form(GOOD, { Origin: 'https://www.' + SITE })).status, 202, 'the www host is listed too');
  assert.equal((await form(undefined, { 'Content-Type': 'text/plain' })).status, 415);
  await app.close();
});

test('honeypot, consent and version failures store nothing', async () => {
  const { app, form } = await start();
  assert.equal((await form(Object.assign({}, GOOD, { website: 'https://spam.example' }))).status, 202, 'bots are told it worked');
  assert.equal((await form(Object.assign({}, GOOD, { consent: false }))).status, 400);
  assert.equal((await form(Object.assign({}, GOOD, { consent_text_id: 'en-v9' }))).status, 409);
  assert.equal((await form(Object.assign({}, GOOD, { email: '', phone: '' }))).status, 400);
  assert.equal(app.store.leads().length, 0);
  await app.close();
});

test('a double click is stored once; a different message is a new lead', async () => {
  const { app, form } = await start();
  assert.equal((await form(GOOD)).status, 202);
  assert.equal((await form(GOOD)).status, 202);
  assert.equal(app.store.leads().length, 1);
  assert.equal((await form(Object.assign({}, GOOD, { message: 'A second, different question.' }))).status, 202);
  assert.equal(app.store.leads().length, 2);
  await app.close();
});

test('rate limits: five per visitor per ten minutes, and an overall hourly cap', async () => {
  let now = new Date('2026-11-21T10:00:00Z').getTime();
  const clock = () => new Date(now);
  const { app, form } = await start({ clock, formLimits: { perKey: 5, windowMinutes: 10, globalPerHour: 8 } });
  const msg = (i) => Object.assign({}, GOOD, { message: 'question ' + i });
  for (let i = 0; i < 5; i += 1) assert.equal((await form(msg(i))).status, 202);
  const limited = await form(msg(99));
  assert.equal(limited.status, 429);
  assert.ok(Number(limited.headers['retry-after']) > 0);
  assert.equal((await form(msg(6), { 'X-Forwarded-For': '198.51.100.9' })).status, 202, 'another visitor is not affected');
  assert.equal((await form(msg(7), { 'X-Forwarded-For': '198.51.100.10' })).status, 202);
  assert.equal((await form(msg(8), { 'X-Forwarded-For': '198.51.100.11' })).status, 202);
  assert.equal((await form(msg(9), { 'X-Forwarded-For': '198.51.100.12' })).status, 429, 'overall cap reached');
  now += 61 * 60000;
  assert.equal((await form(msg(10))).status, 202, 'limits clear with time');
  assert.equal(app.store.leads().length, 9);
  await app.close();
});

test('configuration: form hosts must be plain names and differ from the tool host', () => {
  assert.throws(() => createApp({ dataDir: tmpDir(), quiet: true, formHosts: ['https://x.example'] }), /plain host names/);
  assert.throws(() => createApp({ dataDir: tmpDir(), quiet: true, auth: { publicHost: 'a.example', passwordHash: hashPassword('correct horse battery') }, formHosts: ['a.example'] }), /different/);
});
