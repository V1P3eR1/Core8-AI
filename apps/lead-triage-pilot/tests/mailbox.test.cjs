'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const net = require('node:net');
const path = require('node:path');
const { createApp } = require('../server.cjs');
const M = require('../lib/mailbox.cjs');
const I = require('../lib/intake.cjs');
const { tmpDir, raw } = require('./helpers.cjs');

const SECRET = 'handler-test-secret-not-real';
const FIXTURE = fs.readFileSync(path.join(__dirname, 'fixtures', 'php-lead-email.txt'), 'utf8');

// A tiny plain-TCP IMAP server. It records every command so the tests can
// prove the reader only ever asks read-only questions.
function fakeImap(opts) {
  const log = [];
  const server = net.createServer((sock) => {
    sock.write('* OK fake IMAP ready\r\n');
    let buf = '';
    sock.on('data', (c) => {
      buf += c.toString('latin1');
      let i;
      while ((i = buf.indexOf('\r\n')) !== -1) {
        const line = buf.slice(0, i); buf = buf.slice(i + 2);
        const sp = line.indexOf(' ');
        const tag = line.slice(0, sp); const rest = line.slice(sp + 1);
        const verb = rest.split(' ').slice(0, rest.startsWith('UID ') ? 2 : 1).join(' ');
        log.push(verb === 'LOGIN' ? 'LOGIN' : rest);
        if (verb === 'LOGIN') {
          const ok = rest === 'LOGIN "' + opts.user + '" "' + opts.pass.replace(/"/g, '\\"') + '"';
          sock.write(tag + (ok ? ' OK logged in\r\n' : ' NO bad credentials\r\n'));
        } else if (verb === 'EXAMINE') {
          sock.write('* 3 EXISTS\r\n* OK [UIDVALIDITY ' + opts.uidValidity() + '] ok\r\n' + tag + ' OK [READ-ONLY] done\r\n');
        } else if (verb === 'UID SEARCH') {
          const from = Number(/UID (\d+):\*/.exec(rest)[1]);
          const uids = Object.keys(opts.messages).map(Number);
          // Real servers return the newest message for "n:*" even when it is below n.
          const hit = uids.filter((u) => u >= from);
          const out = hit.length ? hit : [Math.max.apply(null, uids)];
          sock.write('* SEARCH ' + out.join(' ') + '\r\n' + tag + ' OK done\r\n');
        } else if (verb === 'UID FETCH') {
          const uid = Number(rest.split(' ')[2]);
          const body = Buffer.from(opts.messages[uid], 'utf8');
          sock.write('* 1 FETCH (UID ' + uid + ' BODY[TEXT] {' + body.length + '}\r\n');
          sock.write(body); sock.write(')\r\n' + tag + ' OK done\r\n');
        } else if (verb === 'LOGOUT') {
          sock.write('* BYE\r\n' + tag + ' OK bye\r\n'); sock.end();
        } else {
          sock.write(tag + ' BAD unexpected\r\n');
        }
      }
    });
    sock.on('error', () => {});
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve({
    log, port: server.address().port, close: () => new Promise((r) => server.close(r))
  })));
}

function secondLead() {
  return I.encodeLeadEmail({
    v: 1, id: 'b'.repeat(32), submitted_at: '2026-01-02T09:00:00Z', form: 'landing', lang: 'en',
    name: 'Second Person', company: 'Example Ltd', email: 'second@example.com', phone: '', message: 'Please call me about a demo.',
    consent: true, consent_text_id: 'en-v1'
  }, SECRET).body;
}

const READ_ONLY = /^(LOGIN|EXAMINE INBOX|UID SEARCH UID \d+:\* SUBJECT "\[CORE8-LEAD\]"|UID FETCH \d+ \(BODY\.PEEK\[TEXT\]\)|LOGOUT)$/;

test('reader: logs in, opens read-only, fetches only tagged messages newer than the last seen', async () => {
  const imap = await fakeImap({ user: 'office@example.com', pass: 'app "pass" word', uidValidity: () => 7, messages: { 4: FIXTURE, 9: secondLead() } });
  const cfg = { host: '127.0.0.1', port: imap.port, useTls: false, user: 'office@example.com', pass: 'app "pass" word' };

  const all = await M.fetchLeadMessages(cfg, 0);
  assert.equal(all.uidValidity, 7);
  assert.deepEqual(all.messages.map((m) => m.uid), [4, 9]);
  assert.equal(I.parseLeadEmail(all.messages[0].body, { secret: SECRET }).ok, true);

  const newer = await M.fetchLeadMessages(cfg, 4);
  assert.deepEqual(newer.messages.map((m) => m.uid), [9]);
  const none = await M.fetchLeadMessages(cfg, 9);
  assert.deepEqual(none.messages, [], 'the newest message returned for n:* is not re-read');

  assert.ok(imap.log.length >= 12);
  for (const line of imap.log) assert.match(line, READ_ONLY, 'only read-only commands: ' + line);
  assert.ok(!imap.log.some((l) => /STORE|EXPUNGE|APPEND|COPY|MOVE|DELETE|SELECT/i.test(l)));
  await imap.close();
});

test('reader: wrong password and unreachable server fail with a short, secret-free message', async () => {
  const imap = await fakeImap({ user: 'office@example.com', pass: 'right-password', uidValidity: () => 1, messages: { 1: FIXTURE } });
  const base = { host: '127.0.0.1', useTls: false, user: 'office@example.com', pass: 'wrong-password' };
  await assert.rejects(M.fetchLeadMessages(Object.assign({ port: imap.port }, base), 0), (e) => /refused the login/.test(e.message) && !e.message.includes('wrong-password'));
  await imap.close();
  await assert.rejects(M.fetchLeadMessages(Object.assign({ port: imap.port }, base), 0), /Could not connect/);
  await assert.rejects(M.fetchLeadMessages({ host: 'x', port: 1, user: 'a', pass: 'b\r\nc LOGOUT', useTls: false }, 0), /connect|Invalid character/);
});

test('reader: an oversized message is refused', () => {
  const r = M.createReader();
  r.push(Buffer.from('* 1 FETCH (BODY[TEXT] {999999999}\r\n'));
  assert.throws(() => r.take('c1'), /oversized/);
});

test('agent: mailbox check turns form e-mails into leads once, and survives a renumbered mailbox', async () => {
  let validity = 7;
  const messages = { 4: FIXTURE, 9: secondLead(), 10: 'not a lead message at all' };
  const imap = await fakeImap({ user: 'office@example.com', pass: 'app-password-x', uidValidity: () => validity, messages });
  const dataDir = tmpDir();
  const app = createApp({
    dataDir, quiet: true, leadSecret: SECRET,
    mailbox: { host: '127.0.0.1', port: imap.port, useTls: false, user: 'office@example.com', pass: 'app-password-x' }
  });
  const port = await app.listen(0);
  const check = () => raw(port, { method: 'POST', path: '/api/mailbox/check', body: {} });

  const first = (await check()).json.mailbox;
  assert.deepEqual(first.lastResult, { fetched: 3, created: 2, duplicates: 0, rejected: 1 });
  assert.equal(first.lastError, null);
  const again = (await check()).json.mailbox;
  assert.deepEqual(again.lastResult, { fetched: 0, created: 0, duplicates: 0, rejected: 0 });

  validity = 8; // the mail server renumbered everything
  const renumbered = (await check()).json.mailbox;
  assert.deepEqual(renumbered.lastResult, { fetched: 3, created: 0, duplicates: 2, rejected: 1 }, 'nothing is imported twice');

  const state = (await raw(port, { path: '/api/state' })).json;
  assert.equal(state.leads.length, 2);
  assert.ok(state.leads.every((l) => l.source === 'form_email' && l.verified === 'verified' && l.status === 'needs_review'));
  assert.equal(state.config.mailbox.enabled, true);
  assert.equal(state.integrity.ok, true);
  const saved = fs.readFileSync(path.join(dataDir, 'mailbox-state.json'), 'utf8');
  assert.deepEqual(JSON.parse(saved), { uidValidity: 8, lastUid: 10 });
  assert.ok(!JSON.stringify(state).includes('app-password-x') && !saved.includes('app-password-x'), 'the app password is never exposed or stored');
  for (const line of imap.log) assert.match(line, READ_ONLY);
  await imap.close();

  const down = (await check()).json.mailbox;
  assert.match(down.lastError, /Could not connect/);
  assert.equal((await raw(port, { path: '/api/state' })).json.leads.length, 2);
  await app.close();
});

test('agent: mailbox check is refused when no mailbox is configured', async () => {
  const app = createApp({ dataDir: tmpDir(), quiet: true });
  const port = await app.listen(0);
  const r = await raw(port, { method: 'POST', path: '/api/mailbox/check', body: {} });
  assert.equal(r.status, 409);
  await app.close();
});
