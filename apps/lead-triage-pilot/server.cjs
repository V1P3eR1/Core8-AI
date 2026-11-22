'use strict';
/*
 * Core8-AI lead-triage pilot - local single-user server.
 *
 * Binds to 127.0.0.1 only. Serves the review UI and a small JSON API over the
 * append-only event log. It has no code path that sends email or messages:
 * the only outbound connection it can ever make is the optional model call in
 * lib/triage.cjs, and only when the operator explicitly enables it.
 *
 *   node server.cjs                      # offline rules engine
 *   CORE8_PILOT_ENGINE=anthropic ANTHROPIC_API_KEY=... node server.cjs
 *
 * Environment:
 *   CORE8_PILOT_DATA    data folder (default ~/.core8-lead-pilot; must be outside any git repo)
 *   CORE8_PILOT_PORT    port (default 4180)
 *   CORE8_PILOT_ENGINE  "rules" (default) or "anthropic"
 *   CORE8_PILOT_MODEL   model id for the anthropic engine (default claude-sonnet-5-5)
 *   ANTHROPIC_API_KEY   read from the environment only; never written to disk or logs
 *   CORE8_LEAD_SECRET   shared secret with the website form handler; when set, only
 *                       signed lead e-mails are accepted
 *
 * Running on a server (behind a TLS reverse proxy on the same machine):
 *   CORE8_PILOT_PUBLIC_HOST     public host name, e.g. agent.example.com. Setting it
 *                               makes a password mandatory and cookies HTTPS-only.
 *   CORE8_PILOT_PASSWORD_HASH   from `node tools/hash-password.cjs`
 *   CORE8_PILOT_PASSWORD_HASH_FILE  alternative: a file holding the hash, written by
 *                               `node tools/set-password.cjs`. Until it exists the tool
 *                               runs locked: it serves the sign-in page and refuses every login.
 *   CORE8_PILOT_FORM_HOSTS      comma-separated host names of the public website (e.g.
 *                               core8-ai.io,www.core8-ai.io). Requests for those hosts can
 *                               reach exactly one route, POST /api/public/lead, with no
 *                               login; everything else on them is 404.
 *   CORE8_PILOT_CONSENT_IDS     accepted consent text versions (default he-v1,en-v1)
 *   CORE8_PILOT_BIND            127.0.0.1 (default) or 0.0.0.0. The second is only for
 *                               running inside a container with no published port, and
 *                               is refused unless the public host and password are set.
 *
 * Reading the business mailbox (read-only IMAP):
 *   CORE8_PILOT_IMAP_USER / CORE8_PILOT_IMAP_PASS   mailbox address and an app password
 *   CORE8_PILOT_IMAP_HOST (imap.gmail.com) / CORE8_PILOT_IMAP_PORT (993)
 *   CORE8_PILOT_IMAP_MINUTES    how often to check (default 5)
 */
const http = require('node:http');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { openStore } = require('./lib/store.cjs');
const { createTriage, cleanText, MAX_DRAFT } = require('./lib/triage.cjs');
const { computeMetrics, evidenceReport } = require('./lib/metrics.cjs');
const { parseLeadEmail } = require('./lib/intake.cjs');
const { proposeSlots } = require('./lib/slots.cjs');
const { createAuth, readCookie } = require('./lib/auth.cjs');
const { fetchLeadMessages } = require('./lib/mailbox.cjs');
const { validatePublicLead, createLimiter, createDeduper, visitorKey, DEFAULT_CONSENT_IDS } = require('./lib/publicform.cjs');

const PUBLIC = path.join(__dirname, 'public');
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8' };
const CHANNELS = ['website_form', 'email', 'whatsapp', 'phone_note', 'social', 'other'];
const MAX_BODY = 64 * 1024;
const MAX_FORM_BODY = 8 * 1024;
const FORM_PATH = '/api/public/lead';
const COOKIE = 'c8s';
const PUBLIC_PATHS = ['/login.html', '/login.js', '/i18n.js', '/styles.css'];
const CSP = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; form-action 'none'; base-uri 'none'; frame-ancestors 'none'";

class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

function createApp(opts) {
  const clock = opts.clock || (() => new Date());
  const store = openStore(opts.dataDir, { clock });
  const triage = createTriage(opts.triage || {});
  const leadSecret = opts.leadSecret || '';
  const authOpts = opts.auth || {};
  const publicHost = String(authOpts.publicHost || '').toLowerCase();
  if (publicHost && !authOpts.passwordHash && !authOpts.passwordHashFile) {
    throw new Error('CORE8_PILOT_PUBLIC_HOST is set but there is no password. Refusing to run on a public address without a login. Set CORE8_PILOT_PASSWORD_HASH or CORE8_PILOT_PASSWORD_HASH_FILE.');
  }
  const bindHost = opts.bindHost || '127.0.0.1';
  if (!['127.0.0.1', '0.0.0.0'].includes(bindHost)) throw new Error('CORE8_PILOT_BIND must be 127.0.0.1 or 0.0.0.0');
  if (bindHost !== '127.0.0.1' && !publicHost) {
    throw new Error('Refusing to listen beyond this machine without CORE8_PILOT_PUBLIC_HOST and a password.');
  }
  const formHosts = (opts.formHosts || []).map((h) => String(h).trim().toLowerCase()).filter(Boolean);
  if (formHosts.some((h) => !/^[a-z0-9.-]+$/.test(h) || h === publicHost)) throw new Error('CORE8_PILOT_FORM_HOSTS must be plain host names, different from the tool\'s own host');
  const consentIds = opts.consentIds && opts.consentIds.length ? opts.consentIds : DEFAULT_CONSENT_IDS;
  const limiter = createLimiter(Object.assign({ clock }, opts.formLimits || {}));
  const deduper = createDeduper({ clock });
  const auth = createAuth({ passwordHash: authOpts.passwordHash, passwordHashFile: authOpts.passwordHashFile, clock });
  const mailCfg = opts.mailbox && opts.mailbox.user && opts.mailbox.pass ? opts.mailbox : null;
  // Mailbox intake must verify authenticity. Never ingest untrusted mailbox content
  // without a signing key, even when the UI is bound to localhost.
  if (mailCfg && !leadSecret) {
    throw new Error('CORE8_LEAD_SECRET is required when mailbox intake is configured');
  }
  const fetchMail = (opts.mailbox && opts.mailbox.fetchImpl) || fetchLeadMessages;
  const mailState = { enabled: !!mailCfg, lastCheckAt: null, lastResult: null, lastError: null, checking: false };
  const mailStateFile = path.join(store.dir, 'mailbox-state.json');
  const config = {
    engine: triage.engine, model: triage.model, channels: CHANNELS, dataDir: store.dir, signedIntake: !!leadSecret,
    loginRequired: auth.enabled, publicHost: publicHost || null, mailbox: mailState, formHosts
  };

  function send(res, status, body, type, extra) {
    const data = typeof body === 'string' || Buffer.isBuffer(body) ? body : JSON.stringify(body);
    res.writeHead(status, Object.assign({
      'Content-Type': type || 'application/json; charset=utf-8',
      'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
      'X-Frame-Options': 'DENY', 'Content-Security-Policy': CSP
    }, publicHost ? { 'Strict-Transport-Security': 'max-age=31536000' } : {}, extra || {}));
    res.end(data);
  }

  function readJson(req, limit) {
    const MAX = limit || MAX_BODY;
    return new Promise((resolve, reject) => {
      if (!/^application\/json\b/i.test(req.headers['content-type'] || '')) {
        reject(new HttpError(415, 'Content-Type must be application/json')); return;
      }
      let size = 0; let tooLarge = false; const chunks = [];
      req.on('data', (c) => {
        size += c.length;
        if (size > MAX) {
          // Stop buffering but keep draining so the client can read the 413;
          // give up on anything absurdly large.
          tooLarge = true; chunks.length = 0;
          if (size > 16 * MAX) req.destroy();
          return;
        }
        chunks.push(c);
      });
      req.on('end', () => {
        if (tooLarge) { reject(new HttpError(413, 'Request too large')); return; }
        try { resolve(chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : {}); }
        catch (e) { reject(new HttpError(400, 'Invalid JSON')); }
      });
      req.on('error', reject);
    });
  }

  // Loopback only, and only when the browser is really talking to this server:
  // blocks DNS-rebinding and cross-site requests from other pages.
  function guard(req, port) {
    const local = ['127.0.0.1:' + port, 'localhost:' + port];
    const hosts = publicHost ? local.concat([publicHost]) : local;
    if (!hosts.includes(String(req.headers.host || '').toLowerCase())) throw new HttpError(403, 'Forbidden host');
    const origins = local.map((h) => 'http://' + h).concat(publicHost ? ['https://' + publicHost] : []);
    const origin = req.headers.origin;
    if (origin && !origins.includes(origin)) throw new HttpError(403, 'Forbidden origin');
    if (req.method !== 'GET' && req.headers['sec-fetch-site'] && req.headers['sec-fetch-site'] !== 'same-origin') {
      throw new HttpError(403, 'Cross-site request refused');
    }
  }

  function needLead(id) {
    const lead = store.get(id);
    if (!lead) throw new HttpError(404, 'Unknown lead');
    return lead;
  }

  async function runTriage(leadId, text) {
    const result = await triage.run(text);
    // Suggest meeting times only where a conversation is the likely next step.
    result.proposedSlots = ['support', 'not_a_lead'].includes(result.category) ? [] : proposeSlots(clock());
    store.append('triage_completed', leadId, result);
  }

  // One place where a website-form e-mail becomes a lead, whether pasted or read from the mailbox.
  async function ingestLeadEmail(raw) {
    // Only offline, loopback-only fixtures may use unsigned legacy messages.
    // A public pilot must never accept unverified email intake.
    if (!leadSecret && (publicHost || bindHost !== '127.0.0.1')) {
      return { status: 'rejected', error: 'Signed email intake is required in public mode' };
    }
    const parsed = parseLeadEmail(raw, { secret: leadSecret });
    if (!parsed.ok) return { status: 'rejected', error: parsed.error };
    const L = parsed.lead;
    if (store.hasSubmission(L.submissionId)) return { status: 'duplicate' };
    if (new Date(L.submittedAt) > new Date(clock().getTime() + 5 * 60 * 1000)) return { status: 'rejected', error: 'Submission time is in the future' };
    const id = store.nextLeadId();
    const text = L.message || 'Discovery call request from the website form (no message).';
    store.append('lead_added', id, {
      text, channel: 'website_form', receivedAt: L.submittedAt, label: null,
      contact: L.contact, consent: L.consent, submissionId: L.submissionId,
      source: 'form_email', verified: parsed.verified, lang: L.lang
    });
    await runTriage(id, text);
    return { status: 'created', lead: store.get(id) };
  }

  function readMailPosition() {
    try { const j = JSON.parse(fs.readFileSync(mailStateFile, 'utf8')); return { uidValidity: j.uidValidity || null, lastUid: Number(j.lastUid) || 0 }; }
    catch (e) { return { uidValidity: null, lastUid: 0 }; }
  }

  async function checkMailbox() {
    if (!mailCfg) throw new HttpError(409, 'Mailbox reading is not configured');
    if (mailState.checking) return mailState;
    mailState.checking = true;
    try {
      let pos = readMailPosition();
      const res = await fetchMail(mailCfg, pos.lastUid);
      // If the server renumbered the mailbox, start again; duplicates are ignored by submission id.
      let messages = res.messages;
      if (pos.uidValidity !== null && res.uidValidity !== null && res.uidValidity !== pos.uidValidity) {
        pos = { uidValidity: res.uidValidity, lastUid: 0 };
        messages = (await fetchMail(mailCfg, 0)).messages;
      }
      const tally = { fetched: messages.length, created: 0, duplicates: 0, rejected: 0 };
      let maxUid = pos.lastUid;
      for (const msg of messages) {
        const r = await ingestLeadEmail(msg.body);
        if (r.status === 'created') tally.created += 1; else if (r.status === 'duplicate') tally.duplicates += 1; else tally.rejected += 1;
        if (msg.uid > maxUid) maxUid = msg.uid;
      }
      fs.writeFileSync(mailStateFile, JSON.stringify({ uidValidity: res.uidValidity, lastUid: maxUid }) + '\n', { mode: 0o600 });
      mailState.lastResult = tally; mailState.lastError = null;
    } catch (err) {
      // Short reason only; never the address, the password or message content.
      mailState.lastError = String(err && err.message ? err.message : 'Mailbox check failed').slice(0, 160);
    } finally {
      mailState.lastCheckAt = clock().toISOString();
      mailState.checking = false;
    }
    return mailState;
  }

  // The website form. Reached only on a form host, never with a session.
  async function publicForm(req, res, host) {
    const origin = req.headers.origin;
    if (!origin || !formHosts.map((h) => 'https://' + h).includes(origin)) throw new HttpError(403, 'Forbidden origin');
    const wait = limiter.take(visitorKey(req));
    if (wait) return send(res, 429, { error: 'Too many requests' }, null, { 'Retry-After': String(wait) });
    const body = await readJson(req, MAX_FORM_BODY);
    const v = validatePublicLead(body, consentIds);
    if (!v.ok) throw new HttpError(v.status, v.error);
    if (v.honeypot) return send(res, 202, { ok: true });
    const L = v.lead;
    if (deduper.isRepeat(L)) return send(res, 202, { ok: true });
    const id = store.nextLeadId();
    const text = L.message || 'Discovery call request from the website form (no message).';
    store.append('lead_added', id, {
      text, channel: 'website_form', receivedAt: clock().toISOString(), label: null,
      contact: L.contact, consent: L.consent, submissionId: crypto.randomBytes(16).toString('hex'),
      source: 'form_direct', verified: null, lang: L.lang, formHost: host
    });
    await runTriage(id, text);
    return send(res, 202, { ok: true });
  }

  async function api(req, res, url) {
    const parts = url.pathname.split('/').filter(Boolean); // ['api', ...]
    const m = req.method;

    if (m === 'GET' && url.pathname === '/api/state') {
      return send(res, 200, { config, leads: store.leads(), metrics: computeMetrics(store.leads()), integrity: store.verify() });
    }
    if (m === 'GET' && url.pathname === '/api/report') {
      return send(res, 200, evidenceReport(store, config, clock()));
    }
    if (m === 'POST' && url.pathname === '/api/leads') {
      const body = await readJson(req);
      const text = cleanText(body.text);
      if (text.length < 3) throw new HttpError(400, 'Inquiry text is required');
      const channel = CHANNELS.includes(body.channel) ? body.channel : 'other';
      let receivedAt = null;
      if (body.receivedAt) {
        const d = new Date(body.receivedAt);
        if (Number.isNaN(d.getTime())) throw new HttpError(400, 'Invalid received time');
        if (d > clock()) throw new HttpError(400, 'Received time cannot be in the future');
        receivedAt = d.toISOString();
      }
      const id = store.nextLeadId();
      store.append('lead_added', id, { text, channel, receivedAt, label: cleanText(body.label).slice(0, 80) || null });
      await runTriage(id, text);
      return send(res, 201, { lead: store.get(id) });
    }
    if (m === 'POST' && url.pathname === '/api/intake/email') {
      const body = await readJson(req);
      const r = await ingestLeadEmail(body.raw);
      if (r.status === 'rejected') throw new HttpError(422, r.error);
      if (r.status === 'duplicate') return send(res, 200, { duplicate: true });
      return send(res, 201, { lead: r.lead });
    }
    if (m === 'POST' && url.pathname === '/api/mailbox/check') {
      await readJson(req);
      return send(res, 200, { mailbox: await checkMailbox() });
    }
    if (m === 'POST' && parts.length === 4 && parts[1] === 'leads') {
      const lead = needLead(parts[2]);
      const action = parts[3];
      const body = await readJson(req);

      if (action === 'retriage') {
        if (lead.decision) throw new HttpError(409, 'A decision is already recorded for this lead');
        await runTriage(lead.id, lead.text);
        return send(res, 200, { lead: store.get(lead.id) });
      }
      if (action === 'decision') {
        if (!lead.triage) throw new HttpError(409, 'Lead has no draft yet');
        if (lead.decision) throw new HttpError(409, 'A decision is already recorded for this lead');
        if (body.action === 'reject') {
          const reason = cleanText(body.reason).slice(0, 300);
          if (!reason) throw new HttpError(400, 'A reason is required to reject');
          store.append('decision_recorded', lead.id, { action: 'reject', reason, finalText: null });
        } else if (body.action === 'approve') {
          const finalText = cleanText(body.finalText).slice(0, MAX_DRAFT);
          if (!finalText) throw new HttpError(400, 'Cannot approve an empty reply');
          if (/\[(?:Fill in|להשלים)[^\]]*\]/.test(finalText)) throw new HttpError(400, 'Fill in or remove the [placeholder] before approving');
          // "edit" is decided by the server, by comparing against the stored draft.
          const edited = finalText !== cleanText(lead.triage.draft);
          store.append('decision_recorded', lead.id, { action: edited ? 'edit' : 'approve', finalText, reason: null });
        } else {
          throw new HttpError(400, 'Unknown decision');
        }
        return send(res, 200, { lead: store.get(lead.id) });
      }
      if (action === 'sent') {
        if (lead.status !== 'approved') throw new HttpError(409, 'Only an approved reply can be marked as sent');
        store.append('marked_sent', lead.id, { by: 'human', note: 'Operator confirmed they sent the reply themselves' });
        return send(res, 200, { lead: store.get(lead.id) });
      }
    }
    throw new HttpError(404, 'Not found');
  }

  const server = http.createServer(async (req, res) => {
    try {
      const port = server.address().port;
      const host = String(req.headers.host || '').toLowerCase();
      if (formHosts.includes(host)) {
        const p = new URL(req.url, 'http://127.0.0.1').pathname;
        if (req.method === 'POST' && p === FORM_PATH) return await publicForm(req, res, host);
        throw new HttpError(404, 'Not found');
      }
      guard(req, port);
      const url = new URL(req.url, 'http://127.0.0.1:' + port);
      const token = readCookie(req.headers.cookie, COOKIE);
      const cookieFlags = '; Path=/; HttpOnly; SameSite=Strict' + (publicHost ? '; Secure' : '');

      if (req.method === 'POST' && url.pathname === '/api/login') {
        const body = await readJson(req);
        if (!auth.enabled) return send(res, 200, { ok: true, loginRequired: false });
        const r = auth.login(typeof body.password === 'string' ? body.password : '');
        if (r.ok) return send(res, 200, { ok: true }, null, { 'Set-Cookie': COOKIE + '=' + r.token + cookieFlags + '; Max-Age=' + r.maxAgeSeconds });
        if (r.locked) return send(res, 429, { error: 'Too many wrong passwords. Try again later.' }, null, { 'Retry-After': String(r.retryAfterSeconds) });
        if (r.notSet) return send(res, 503, { error: 'No password has been set yet. The owner sets it on the server.' });
        return send(res, 401, { error: 'Wrong password' });
      }
      if (req.method === 'POST' && url.pathname === '/api/logout') {
        await readJson(req);
        auth.logout(token);
        return send(res, 200, { ok: true }, null, { 'Set-Cookie': COOKIE + '=' + cookieFlags + '; Max-Age=0' });
      }
      if (auth.enabled && !auth.check(token) && !(req.method === 'GET' && PUBLIC_PATHS.includes(url.pathname))) {
        if (url.pathname.startsWith('/api/')) throw new HttpError(401, 'Login required');
        return send(res, 302, '', 'text/plain; charset=utf-8', { Location: '/login.html' });
      }
      if (url.pathname.startsWith('/api/')) return await api(req, res, url);
      if (req.method !== 'GET') throw new HttpError(405, 'Method not allowed');
      const rel = url.pathname === '/' ? '/index.html' : url.pathname;
      const file = path.resolve(PUBLIC, '.' + rel);
      if (!file.startsWith(PUBLIC + path.sep) || !TYPES[path.extname(file)] || !fs.existsSync(file)) throw new HttpError(404, 'Not found');
      return send(res, 200, fs.readFileSync(file), TYPES[path.extname(file)]);
    } catch (err) {
      const status = err instanceof HttpError ? err.status : 500;
      // Internal errors are not echoed to the browser.
      send(res, status, { error: status === 500 ? 'Internal error' : err.message });
      if (status === 500 && !opts.quiet) console.error('[pilot] ' + (err && err.message));
    }
  });

  return {
    server, store, config, checkMailbox, auth,
    listen: (port) => new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(port, bindHost, () => resolve(server.address().port));
    }),
    close: () => new Promise((resolve) => server.close(resolve))
  };
}

module.exports = { createApp, CHANNELS };

if (require.main === module) {
  const app = createApp({
    dataDir: process.env.CORE8_PILOT_DATA || path.join(os.homedir(), '.core8-lead-pilot'),
    triage: {
      engine: process.env.CORE8_PILOT_ENGINE || 'rules',
      apiKey: process.env.ANTHROPIC_API_KEY || '',
      model: process.env.CORE8_PILOT_MODEL || 'claude-sonnet-5-5',
      fetchImpl: globalThis.fetch
    },
    leadSecret: process.env.CORE8_LEAD_SECRET || '',
    formHosts: (process.env.CORE8_PILOT_FORM_HOSTS || '').split(','),
    consentIds: (process.env.CORE8_PILOT_CONSENT_IDS || '').split(',').map((s) => s.trim()).filter(Boolean),
    bindHost: process.env.CORE8_PILOT_BIND || '127.0.0.1',
    auth: { publicHost: process.env.CORE8_PILOT_PUBLIC_HOST || '', passwordHash: process.env.CORE8_PILOT_PASSWORD_HASH || '', passwordHashFile: process.env.CORE8_PILOT_PASSWORD_HASH_FILE || '' },
    mailbox: {
      user: process.env.CORE8_PILOT_IMAP_USER || '', pass: process.env.CORE8_PILOT_IMAP_PASS || '',
      host: process.env.CORE8_PILOT_IMAP_HOST || 'imap.gmail.com', port: Number(process.env.CORE8_PILOT_IMAP_PORT) || 993
    }
  });
  app.listen(Number(process.env.CORE8_PILOT_PORT) || 4180).then((port) => {
    console.log('Core8-AI lead-triage pilot  http://127.0.0.1:' + port + '/');
    console.log('Engine: ' + app.config.engine + (app.config.model ? ' (' + app.config.model + ')' : ' (offline, no network)'));
    if ((process.env.CORE8_PILOT_ENGINE || 'rules') === 'anthropic' && app.config.engine !== 'anthropic') {
      console.log('ANTHROPIC_API_KEY is not set, so the offline rules engine is in use.');
    }
    console.log('Intake: ' + (app.config.signedIntake ? 'signed lead e-mails only' : 'unsigned lead e-mails accepted (set CORE8_LEAD_SECRET to require a signature)'));
    console.log('Login:  ' + (app.config.loginRequired ? (app.auth.passwordSet() ? 'password required' : 'LOCKED - no password set yet (run: node tools/set-password.cjs)') : 'OFF (local use only; never expose this port)'));
    if (app.config.formHosts.length) console.log('Form:   website form accepted from ' + app.config.formHosts.join(', ') + ' (POST /api/public/lead, no login)');
    if (app.config.publicHost) console.log('Public: https://' + app.config.publicHost + ' (through a TLS reverse proxy on this machine)');
    if (app.config.mailbox.enabled) {
      const minutes = Math.max(1, Number(process.env.CORE8_PILOT_IMAP_MINUTES) || 5);
      console.log('Mailbox: read-only check every ' + minutes + ' min for [CORE8-LEAD] messages');
      app.checkMailbox();
      setInterval(() => { app.checkMailbox(); }, minutes * 60000).unref();
    } else {
      console.log('Mailbox: not configured (paste lead e-mails in by hand)');
    }
    console.log('Data:   ' + app.store.file);
    console.log('This tool drafts replies only. It cannot send anything.');
  }).catch((err) => { console.error(err.message); process.exit(1); });
}
