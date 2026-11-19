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
 */
const http = require('node:http');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { openStore } = require('./lib/store.cjs');
const { createTriage, cleanText, MAX_DRAFT } = require('./lib/triage.cjs');
const { computeMetrics, evidenceReport } = require('./lib/metrics.cjs');

const PUBLIC = path.join(__dirname, 'public');
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8' };
const CHANNELS = ['website_form', 'email', 'whatsapp', 'phone_note', 'social', 'other'];
const MAX_BODY = 64 * 1024;
const CSP = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; form-action 'none'; base-uri 'none'; frame-ancestors 'none'";

class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

function createApp(opts) {
  const clock = opts.clock || (() => new Date());
  const store = openStore(opts.dataDir, { clock });
  const triage = createTriage(opts.triage || {});
  const config = { engine: triage.engine, model: triage.model, channels: CHANNELS, dataDir: store.dir };

  function send(res, status, body, type) {
    const data = typeof body === 'string' || Buffer.isBuffer(body) ? body : JSON.stringify(body);
    res.writeHead(status, {
      'Content-Type': type || 'application/json; charset=utf-8',
      'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
      'Content-Security-Policy': CSP
    });
    res.end(data);
  }

  function readJson(req) {
    return new Promise((resolve, reject) => {
      if (!/^application\/json\b/i.test(req.headers['content-type'] || '')) {
        reject(new HttpError(415, 'Content-Type must be application/json')); return;
      }
      let size = 0; let tooLarge = false; const chunks = [];
      req.on('data', (c) => {
        size += c.length;
        if (size > MAX_BODY) {
          // Stop buffering but keep draining so the client can read the 413;
          // give up on anything absurdly large.
          tooLarge = true; chunks.length = 0;
          if (size > 16 * MAX_BODY) req.destroy();
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
    const allowed = ['127.0.0.1:' + port, 'localhost:' + port];
    if (!allowed.includes(req.headers.host || '')) throw new HttpError(403, 'Forbidden host');
    const origin = req.headers.origin;
    if (origin && !allowed.map((h) => 'http://' + h).includes(origin)) throw new HttpError(403, 'Forbidden origin');
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
    store.append('triage_completed', leadId, result);
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
      guard(req, port);
      const url = new URL(req.url, 'http://127.0.0.1:' + port);
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
    server, store, config,
    listen: (port) => new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(port, '127.0.0.1', () => resolve(server.address().port));
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
    }
  });
  app.listen(Number(process.env.CORE8_PILOT_PORT) || 4180).then((port) => {
    console.log('Core8-AI lead-triage pilot  http://127.0.0.1:' + port + '/');
    console.log('Engine: ' + app.config.engine + (app.config.model ? ' (' + app.config.model + ')' : ' (offline, no network)'));
    if ((process.env.CORE8_PILOT_ENGINE || 'rules') === 'anthropic' && app.config.engine !== 'anthropic') {
      console.log('ANTHROPIC_API_KEY is not set, so the offline rules engine is in use.');
    }
    console.log('Data:   ' + app.store.file);
    console.log('This tool drafts replies only. It cannot send anything.');
  }).catch((err) => { console.error(err.message); process.exit(1); });
}
