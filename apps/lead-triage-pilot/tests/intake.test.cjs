'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const I = require('../lib/intake.cjs');
const { proposeSlots } = require('../lib/slots.cjs');
const { createApp } = require('../server.cjs');
const { tmpDir, raw } = require('./helpers.cjs');

const base = () => ({ v: 1, id: 'a1b2c3d4e5f60718', submitted_at: '2026-11-20T08:00:00Z', form: 'landing', lang: 'he', name: 'דנה לדוגמה', company: 'חברה לדוגמה', email: 'dana@example.invalid', phone: '', message: 'מעוניינים בשיחת אפיון', consent: true, consent_text_id: 'he-v1' });
const SECRET = 'test-shared-secret-not-real';

test('round trip: encode, parse, verify signature', () => {
  const mail = I.encodeLeadEmail(base(), SECRET);
  assert.equal(mail.subject, '[CORE8-LEAD] v1');
  assert.ok(/^[\x00-\x7f]*$/.test(mail.body), 'body is pure ASCII');
  assert.ok(!mail.body.includes('dana@'), 'contact details are not in the readable part');
  const r = I.parseLeadEmail(mail.body, { secret: SECRET });
  assert.equal(r.ok, true);
  assert.equal(r.verified, 'verified');
  assert.deepEqual(r.lead.contact, { name: 'דנה לדוגמה', company: 'חברה לדוגמה', email: 'dana@example.invalid', phone: null });
  assert.equal(r.lead.message, 'מעוניינים בשיחת אפיון');
  assert.deepEqual(r.lead.consent, { given: true, textId: 'he-v1' });
  assert.equal(r.lead.submittedAt, '2026-11-20T08:00:00.000Z');
});

test('survives mail-client damage: CRLF, quoting, quoted-printable, surrounding text', () => {
  const body = I.encodeLeadEmail(base(), SECRET).body;
  const variants = [
    body.replace(/\n/g, '\r\n'),
    'Forwarded message\n\n' + body.split('\n').map((l) => '> ' + l).join('\n'),
    body.replace(/([A-Za-z0-9_-]{40})/g, '$1=\n'),
    'Hi,\n\n' + body + '\n--\nSent from a phone'
  ];
  for (const v of variants) {
    const r = I.parseLeadEmail(v, { secret: SECRET });
    assert.equal(r.ok, true, r.error);
    assert.equal(r.lead.contact.email, 'dana@example.invalid');
  }
});

test('with a secret: unsigned, wrongly signed and altered blocks are refused', () => {
  assert.match(I.parseLeadEmail(I.encodeLeadEmail(base(), '').body, { secret: SECRET }).error, /not signed/);
  assert.match(I.parseLeadEmail(I.encodeLeadEmail(base(), 'another-secret').body, { secret: SECRET }).error, /Signature does not match/);
  const forged = I.encodeLeadEmail(Object.assign(base(), { email: 'attacker@example.invalid' }), SECRET).body.split('\n');
  const good = I.encodeLeadEmail(base(), SECRET).body.split('\n');
  const mixed = forged.slice(0, -2).concat(good.slice(-2)).join('\n'); // forged block, genuine signature
  assert.match(I.parseLeadEmail(mixed, { secret: SECRET }).error, /Signature does not match/);
});

test('without a secret: accepted but marked unsigned', () => {
  const r = I.parseLeadEmail(I.encodeLeadEmail(base(), '').body);
  assert.equal(r.ok, true);
  assert.equal(r.verified, 'unsigned');
});

test('invalid submissions are refused with a reason', () => {
  const bad = (patch) => I.parseLeadEmail(I.encodeLeadEmail(Object.assign(base(), patch), '').body);
  assert.match(bad({ consent: false }).error, /no consent/);
  assert.match(bad({ consent: 'true' }).error, /no consent/);
  assert.match(bad({ name: '  ' }).error, /Name is missing/);
  assert.match(bad({ email: 'nope' }).error, /Invalid e-mail/);
  assert.match(bad({ email: '', phone: '' }).error, /Neither e-mail nor phone/);
  assert.match(bad({ email: '', phone: '12' }).error, /Invalid phone/);
  assert.match(bad({ id: 'xyz' }).error, /submission id/);
  assert.match(bad({ submitted_at: 'yesterday' }).error, /submission time/);
  assert.match(bad({ v: 2 }).error, /version/);
  assert.match(I.parseLeadEmail('just a normal e-mail').error, /No CORE8 LEAD v1 block/);
  assert.match(I.parseLeadEmail(I.BEGIN + '\n!!!!\n' + I.END).error, /base64url/);
  assert.match(I.parseLeadEmail(I.BEGIN + '\nbm90IGpzb24\n' + I.END).error, /valid JSON/);
  const two = I.encodeLeadEmail(base(), '').body;
  assert.match(I.parseLeadEmail(two + '\n' + two).error, /More than one/);
  assert.equal(bad({ email: '', phone: '+972 50 000 0000' }).ok, true);
});

test('fields are cleaned and length-limited', () => {
  const r = I.parseLeadEmail(I.encodeLeadEmail(Object.assign(base(), { name: 'A\u0000B‮', message: 'x'.repeat(5000), company: '' }), '').body);
  assert.equal(r.lead.contact.name, 'A B');
  assert.equal(r.lead.message.length, 2000);
  assert.equal(r.lead.contact.company, null);
});

test('proposed slots: next working days, never today, flagged as not calendar-checked', () => {
  const s = proposeSlots(new Date(2026, 10, 19, 10)); // Thursday
  assert.deepEqual(s.map((x) => x.date), ['2026-11-22', '2026-11-23', '2026-11-24']);
  assert.ok(s.every((x) => x.calendarChecked === false));
  assert.equal(proposeSlots(new Date(2026, 10, 21, 23, 59), { count: 1 })[0].date, '2026-11-22');
});

test('API: signed intake creates a lead with contact, consent and slots; duplicates and forgeries are refused', async () => {
  const app = createApp({ dataDir: tmpDir(), quiet: true, leadSecret: SECRET });
  const port = await app.listen(0);
  const post = (body) => raw(port, { method: 'POST', path: '/api/intake/email', body });
  const good = I.encodeLeadEmail(Object.assign(base(), { submitted_at: new Date(Date.now() - 60000).toISOString() }), SECRET).body;

  const r = await post({ raw: good });
  assert.equal(r.status, 201);
  const lead = r.json.lead;
  assert.equal(lead.source, 'form_email');
  assert.equal(lead.verified, 'verified');
  assert.equal(lead.channel, 'website_form');
  assert.equal(lead.contact.name, 'דנה לדוגמה');
  assert.equal(lead.consent.textId, 'he-v1');
  assert.equal(lead.status, 'needs_review');
  assert.equal(lead.triage.proposedSlots.length, 3);

  const dup = await post({ raw: good });
  assert.equal(dup.status, 200);
  assert.equal(dup.json.duplicate, true);
  assert.equal(app.store.leads().length, 1);

  assert.equal((await post({ raw: I.encodeLeadEmail(Object.assign(base(), { id: 'ffffffffffffffff' }), 'wrong').body })).status, 422);
  assert.equal((await post({ raw: 'hello' })).status, 422);
  const future = I.encodeLeadEmail(Object.assign(base(), { id: 'eeeeeeeeeeeeeeee', submitted_at: '2999-01-01T00:00:00Z' }), SECRET).body;
  assert.equal((await post({ raw: future })).status, 422);
  assert.equal(app.store.leads().length, 1, 'nothing invalid was stored');

  const state = (await raw(port, { path: '/api/state' })).json;
  assert.equal(state.config.signedIntake, true);
  const report = await raw(port, { path: '/api/report' });
  assert.ok(!/dana@|דנה|חברה לדוגמה/.test(report.text), 'evidence report stays redacted');
  assert.ok(!JSON.stringify(app.store.events()).includes(SECRET), 'secret never reaches the log');
  await app.close();
});

test('API: support and spam leads get no meeting suggestions', async () => {
  const app = createApp({ dataDir: tmpDir(), quiet: true });
  const port = await app.listen(0);
  const mk = (id, message) => I.encodeLeadEmail(Object.assign(base(), { id, message, submitted_at: new Date(Date.now() - 1000).toISOString() }), '').body;
  const a = await raw(port, { method: 'POST', path: '/api/intake/email', body: { raw: mk('1111111111111111', 'The dashboard is not working') } });
  assert.equal(a.json.lead.verified, 'unsigned');
  assert.deepEqual(a.json.lead.triage.proposedSlots, []);
  const b = await raw(port, { method: 'POST', path: '/api/intake/email', body: { raw: mk('2222222222222222', '') } });
  assert.match(b.json.lead.text, /no message/);
  assert.equal(b.json.lead.triage.proposedSlots.length, 3);
  await app.close();
});

test('fixture produced by the PHP form handler parses and verifies', () => {
  const file = path.join(__dirname, 'fixtures', 'php-lead-email.txt');
  const r = I.parseLeadEmail(fs.readFileSync(file, 'utf8'), { secret: 'handler-test-secret-not-real' });
  assert.equal(r.ok, true, r.error);
  assert.equal(r.verified, 'verified');
  assert.equal(r.lead.contact.name, 'דנה לדוגמה');
  assert.equal(r.lead.contact.email, 'dana@example.invalid');
  assert.equal(r.lead.lang, 'he');
});
