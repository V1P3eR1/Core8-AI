'use strict';
/*
 * Lead e-mail format "CORE8 LEAD v1": how a website form submission travels
 * to the business mailbox and into this tool.
 *
 * The form handler (apps/landing/server/lead.php, separate PR) sends a plain
 * text e-mail whose body contains one machine-readable block:
 *
 *   -----BEGIN CORE8 LEAD v1-----
 *   <base64url(JSON), wrapped; ASCII only so mail transfer encodings cannot damage it>
 *   -----END CORE8 LEAD v1-----
 *   sig: <hex HMAC-SHA256 of the unwrapped base64url text, or "none">
 *
 * With a shared secret configured on both sides the signature proves the block
 * came from the form handler and was not altered. Anyone can send mail to a
 * mailbox, so without a secret a lead is accepted but marked "unsigned".
 * Either way the content is untrusted text for a human to review.
 */
const crypto = require('node:crypto');

const BEGIN = '-----BEGIN CORE8 LEAD v1-----';
const END = '-----END CORE8 LEAD v1-----';
const SUBJECT_TAG = '[CORE8-LEAD]';

const clean = (v, max) => String(v === null || v === undefined ? '' : v)
  .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f‪-‮⁦-⁩]/g, ' ')
  .replace(/\r\n?/g, '\n').trim().slice(0, max);
const validEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v) && v.length <= 200;
const validPhone = (v) => /^\+?[\d\s().-]{7,20}$/.test(v) && (v.match(/\d/g) || []).length >= 7;
const sign = (b64, secret) => crypto.createHmac('sha256', secret).update(b64).digest('hex');

function encodeLeadEmail(payload, secret) {
  const b64 = Buffer.from(JSON.stringify(payload), 'utf8').toString('base64url');
  const wrapped = b64.match(/.{1,60}/g).join('\n');
  return {
    subject: SUBJECT_TAG + ' v1',
    body: ['New website inquiry (Core8-AI landing page).', 'Open the lead-triage tool to review it.', '', BEGIN, wrapped, END,
      'sig: ' + (secret ? sign(b64, secret) : 'none'), ''].join('\n')
  };
}

function fail(error) { return { ok: false, error }; }

function parseLeadEmail(raw, opts) {
  const secret = (opts && opts.secret) || '';
  // Undo quoted-printable soft breaks and "=3D" in case a relay re-encoded the mail.
  const text = String(raw || '').replace(/\r\n?/g, '\n').replace(/=\n/g, '').replace(/=3D/gi, '=');
  const start = text.indexOf(BEGIN);
  const end = text.indexOf(END);
  if (start === -1 || end === -1 || end < start) return fail('No CORE8 LEAD v1 block found');
  if (text.indexOf(BEGIN, start + 1) !== -1) return fail('More than one lead block in the message');
  const b64 = text.slice(start + BEGIN.length, end).replace(/[\s>]/g, '');
  if (!b64 || !/^[A-Za-z0-9_-]+$/.test(b64) || b64.length > 12000) return fail('Lead block is not valid base64url');
  const sigMatch = /^\s*>?\s*sig:\s*([0-9a-f]{64}|none)\s*$/m.exec(text.slice(end + END.length));
  const sig = sigMatch ? sigMatch[1] : 'none';

  let verified = 'unsigned';
  if (secret) {
    if (sig === 'none') return fail('Lead is not signed, and this tool requires a signature');
    const want = Buffer.from(sign(b64, secret), 'hex');
    const got = Buffer.from(sig, 'hex');
    if (want.length !== got.length || !crypto.timingSafeEqual(want, got)) return fail('Signature does not match: not from the form handler, or altered');
    verified = 'verified';
  }

  let p;
  try { p = JSON.parse(Buffer.from(b64, 'base64url').toString('utf8')); } catch (e) { return fail('Lead block does not contain valid JSON'); }
  if (!p || typeof p !== 'object' || Array.isArray(p) || p.v !== 1) return fail('Unsupported lead format version');
  if (typeof p.id !== 'string' || !/^[0-9a-f]{16,64}$/.test(p.id)) return fail('Missing or invalid submission id');
  const at = new Date(p.submitted_at);
  if (typeof p.submitted_at !== 'string' || Number.isNaN(at.getTime())) return fail('Missing or invalid submission time');
  if (p.consent !== true) return fail('Submission has no consent; it must not be processed');
  const name = clean(p.name, 120);
  const email = clean(p.email, 200);
  const phone = clean(p.phone, 30);
  if (!name) return fail('Name is missing');
  if (email && !validEmail(email)) return fail('Invalid e-mail address');
  if (phone && !validPhone(phone)) return fail('Invalid phone number');
  if (!email && !phone) return fail('Neither e-mail nor phone was provided');

  return {
    ok: true,
    verified,
    lead: {
      submissionId: p.id, submittedAt: at.toISOString(),
      form: clean(p.form, 40) || 'unknown', lang: p.lang === 'en' ? 'en' : 'he',
      contact: { name, company: clean(p.company, 120) || null, email: email || null, phone: phone || null },
      message: clean(p.message, 2000),
      consent: { given: true, textId: clean(p.consent_text_id, 80) || null }
    }
  };
}

module.exports = { encodeLeadEmail, parseLeadEmail, BEGIN, END, SUBJECT_TAG };
