'use strict';
/*
 * Public website-form intake: the one route of this tool that needs no login.
 *
 * The landing page posts its form straight here (same origin, through the
 * reverse proxy), so no e-mail, mailbox password or shared secret is involved.
 * Everything in a submission is untrusted text for a human to review; this
 * module only decides whether to accept it, never what to do with it.
 *
 * Accepts only what the form sends, from a configured host, with consent:
 *   - honeypot field "website" filled -> pretend success, store nothing
 *   - consent must be true and its text id on the allow-list (else 409)
 *   - name, and an e-mail or a phone number
 *   - rate limits per visitor address and overall (else 429)
 *   - the same person sending the same thing twice within ten minutes is stored once
 */
const crypto = require('node:crypto');
const { clean, validEmail, validPhone } = require('./intake.cjs');

const DEFAULT_CONSENT_IDS = ['he-v1', 'en-v1'];

function validatePublicLead(body, consentIds) {
  const b = body && typeof body === 'object' && !Array.isArray(body) ? body : {};
  if (clean(b.website, 200)) return { ok: true, honeypot: true };
  if (b.consent !== true) return { ok: false, status: 400, error: 'Consent is required' };
  const textId = clean(b.consent_text_id, 40);
  if (!(consentIds || DEFAULT_CONSENT_IDS).includes(textId)) return { ok: false, status: 409, error: 'Unknown consent text version' };
  const name = clean(b.name, 120);
  const email = clean(b.email, 200);
  const phone = clean(b.phone, 30);
  if (!name) return { ok: false, status: 400, error: 'Name is required' };
  if (email && !validEmail(email)) return { ok: false, status: 400, error: 'Invalid e-mail address' };
  if (phone && !validPhone(phone)) return { ok: false, status: 400, error: 'Invalid phone number' };
  if (!email && !phone) return { ok: false, status: 400, error: 'An e-mail address or a phone number is required' };
  return {
    ok: true,
    lead: {
      lang: b.lang === 'en' ? 'en' : 'he',
      contact: { name, company: clean(b.company, 120) || null, email: email || null, phone: phone || null },
      message: clean(b.message, 2000),
      consent: { given: true, textId }
    }
  };
}

// Sliding-window limiter. Keys are hashed so visitor addresses are not kept in memory as-is.
function createLimiter(opts) {
  const perKey = opts.perKey || 5;
  const windowMs = (opts.windowMinutes || 10) * 60000;
  const globalMax = opts.globalPerHour || 60;
  const clock = opts.clock || (() => new Date());
  const salt = crypto.randomBytes(16);
  const hits = new Map();
  let global = [];
  return {
    // Returns 0 when allowed (and records the hit), else seconds to wait.
    take(key) {
      const now = clock().getTime();
      global = global.filter((t) => t > now - 3600000);
      if (global.length >= globalMax) return Math.ceil((global[0] + 3600000 - now) / 1000);
      const k = crypto.createHmac('sha256', salt).update(String(key)).digest('base64url');
      const list = (hits.get(k) || []).filter((t) => t > now - windowMs);
      if (list.length >= perKey) { hits.set(k, list); return Math.ceil((list[0] + windowMs - now) / 1000); }
      list.push(now); hits.set(k, list); global.push(now);
      if (hits.size > 5000) for (const [kk, v] of hits) if (!v.some((t) => t > now - windowMs)) hits.delete(kk);
      return 0;
    }
  };
}

// Remembers recent submissions so a double click or a resend is stored once.
function createDeduper(opts) {
  const windowMs = (opts && opts.windowMinutes || 10) * 60000;
  const clock = (opts && opts.clock) || (() => new Date());
  const seen = new Map();
  return {
    isRepeat(lead) {
      const now = clock().getTime();
      for (const [k, t] of seen) if (t <= now - windowMs) seen.delete(k);
      const c = lead.contact;
      const k = crypto.createHash('sha256').update(JSON.stringify([c.name, c.email, c.phone, lead.message].map((v) => String(v || '').toLowerCase()))).digest('hex');
      if (seen.has(k)) return true;
      seen.set(k, now);
      return false;
    }
  };
}

// The reverse proxy (Caddy) sets X-Forwarded-For itself and drops what the
// client sent, so its last entry is the visitor. Without a proxy, use the socket.
function visitorKey(req) {
  const xff = String(req.headers['x-forwarded-for'] || '').split(',').map((s) => s.trim()).filter(Boolean);
  return xff.length ? xff[xff.length - 1] : (req.socket && req.socket.remoteAddress) || 'unknown';
}

module.exports = { validatePublicLead, createLimiter, createDeduper, visitorKey, DEFAULT_CONSENT_IDS };
