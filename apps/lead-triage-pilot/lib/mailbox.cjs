'use strict';
/*
 * Read-only mailbox reader for website-form leads (IMAP over TLS).
 *
 * What it does, and nothing more:
 *   - logs in with an app password supplied through the environment;
 *   - opens the inbox with EXAMINE, which is read-only by definition;
 *   - asks the mail server for messages whose SUBJECT contains [CORE8-LEAD],
 *     so other mail is never downloaded;
 *   - fetches each body with BODY.PEEK, which does not mark it as read.
 * It never sends, moves, flags or deletes anything.
 */
const net = require('node:net');
const tls = require('node:tls');

const MAX_LITERAL = 256 * 1024;
const MAX_PER_POLL = 50;
const SUBJECT_TAG = '[CORE8-LEAD]';

const quote = (s) => {
  if (/[\r\n\0]/.test(s)) throw new Error('Invalid character in mailbox credentials');
  return '"' + String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
};

// Incremental parser for IMAP responses, including {n} literals.
function createReader() {
  let buf = Buffer.alloc(0);
  return {
    push(chunk) { buf = Buffer.concat([buf, chunk]); },
    // Returns { items, status, text } once the line tagged `tag` has arrived, else null.
    take(tag) {
      const items = [];
      let p = 0;
      for (;;) {
        const eol = buf.indexOf('\r\n', p);
        if (eol === -1) return null;
        const line = buf.slice(p, eol).toString('latin1');
        const lit = /\{(\d+)\}$/.exec(line);
        if (lit) {
          const n = Number(lit[1]);
          if (n > MAX_LITERAL) throw new Error('Mail server sent an oversized message; skipped for safety');
          if (buf.length < eol + 2 + n) return null;
          items.push({ line, literal: buf.slice(eol + 2, eol + 2 + n) });
          p = eol + 2 + n;
          continue;
        }
        items.push({ line });
        p = eol + 2;
        if (tag === null || line.startsWith(tag + ' ')) {
          buf = buf.slice(p);
          const m = /^\S+ (\S+) ?(.*)$/.exec(line) || [];
          return { items, status: m[1] || '', text: m[2] || '' };
        }
      }
    }
  };
}

function open(cfg) {
  return new Promise((resolve, reject) => {
    const onError = (e) => reject(new Error('Could not connect to the mail server (' + (e.code || 'error') + ')'));
    const sock = cfg.useTls === false
      ? net.connect({ host: cfg.host, port: cfg.port }, () => resolve(sock))
      : tls.connect({ host: cfg.host, port: cfg.port, servername: cfg.host, minVersion: 'TLSv1.2' }, () => resolve(sock));
    sock.once('error', onError);
  });
}

async function fetchLeadMessages(cfg, sinceUid) {
  if (!cfg.user || !cfg.pass) throw new Error('Mailbox user and app password are required');
  const sock = await open(cfg);
  const reader = createReader();
  let waiting = null;
  let failed = null;
  const pump = () => {
    if (!waiting) return;
    try { const r = reader.take(waiting.tag); if (r) { const w = waiting; waiting = null; w.resolve(r); } }
    catch (e) { const w = waiting; waiting = null; w.reject(e); }
  };
  sock.on('data', (c) => { reader.push(c); pump(); });
  sock.on('error', (e) => { failed = e; if (waiting) { const w = waiting; waiting = null; w.reject(new Error('Mail connection failed')); } });
  sock.on('close', () => { if (waiting) { const w = waiting; waiting = null; w.reject(new Error('Mail server closed the connection')); } });
  sock.setTimeout(cfg.timeoutMs || 20000, () => sock.destroy(new Error('timeout')));
  const until = (tag) => new Promise((resolve, reject) => { if (failed) return reject(new Error('Mail connection failed')); waiting = { tag, resolve, reject }; pump(); });
  let n = 0;
  const cmd = (line) => { const tag = 'c' + (++n); sock.write(tag + ' ' + line + '\r\n'); return until(tag); };

  try {
    const greeting = await until(null);
    if (!/^\* OK/i.test(greeting.items[0].line)) throw new Error('Unexpected greeting from the mail server');

    const login = await cmd('LOGIN ' + quote(cfg.user) + ' ' + quote(cfg.pass));
    if (login.status !== 'OK') throw new Error('The mail server refused the login. Check the address and the app password.');

    const box = await cmd('EXAMINE INBOX');
    if (box.status !== 'OK') throw new Error('Could not open the inbox');
    let uidValidity = null;
    for (const it of box.items) { const m = /UIDVALIDITY (\d+)/i.exec(it.line); if (m) uidValidity = Number(m[1]); }

    const from = Math.max(0, Number(sinceUid) || 0) + 1;
    const search = await cmd('UID SEARCH UID ' + from + ':* SUBJECT ' + quote(SUBJECT_TAG));
    if (search.status !== 'OK') throw new Error('The mail server refused the search');
    let uids = [];
    for (const it of search.items) { const m = /^\* SEARCH(.*)$/i.exec(it.line); if (m) uids = uids.concat(m[1].trim().split(/\s+/).filter(Boolean).map(Number)); }
    // "n:*" always matches the newest message, even when it is older than n.
    uids = uids.filter((u) => Number.isInteger(u) && u >= from).sort((a, b) => a - b).slice(0, MAX_PER_POLL);

    const messages = [];
    for (const uid of uids) {
      const res = await cmd('UID FETCH ' + uid + ' (BODY.PEEK[TEXT])');
      const withBody = res.items.find((it) => it.literal && /FETCH/i.test(it.line));
      if (res.status === 'OK' && withBody) messages.push({ uid, body: withBody.literal.toString('utf8') });
    }
    await cmd('LOGOUT').catch(() => {});
    return { uidValidity, messages };
  } finally {
    sock.destroy();
  }
}

module.exports = { fetchLeadMessages, createReader, SUBJECT_TAG, MAX_PER_POLL };
