'use strict';
/*
 * Single-user login for the lead-triage tool when it runs on a server.
 *
 * - The password is never stored: only a scrypt hash, supplied through the
 *   environment (make one with `node tools/hash-password.cjs`).
 * - Sessions are random 256-bit tokens held in memory; restarting the service
 *   signs everyone out.
 * - After five wrong passwords, logins are locked for fifteen minutes. The lock
 *   is global, not per address: there is one user, and behind a reverse proxy
 *   every request has the proxy's address. The cost is that an attacker can
 *   keep the owner locked out; the benefit is that guessing stays slow.
 */
const crypto = require('node:crypto');

const N = 16384, R = 8, P = 1, KEYLEN = 64;

function hashPassword(password) {
  if (typeof password !== 'string' || password.length < 12) throw new Error('Password must be at least 12 characters');
  const salt = crypto.randomBytes(16);
  const key = crypto.scryptSync(password, salt, KEYLEN, { N, r: R, p: P });
  return ['scrypt', N, R, P, salt.toString('base64url'), key.toString('base64url')].join('$');
}

function verifyPassword(password, stored) {
  const parts = String(stored || '').split('$');
  if (parts.length !== 6 || parts[0] !== 'scrypt') return false;
  const [, n, r, p, salt, key] = parts;
  const want = Buffer.from(key, 'base64url');
  if (!want.length || typeof password !== 'string' || password.length > 1024) return false;
  let got;
  try { got = crypto.scryptSync(password, Buffer.from(salt, 'base64url'), want.length, { N: Number(n), r: Number(r), p: Number(p) }); }
  catch (e) { return false; }
  return got.length === want.length && crypto.timingSafeEqual(got, want);
}

function validHash(stored) { return /^scrypt\$\d+\$\d+\$\d+\$[A-Za-z0-9_-]{16,}\$[A-Za-z0-9_-]{40,}$/.test(String(stored || '')); }

function createAuth(opts) {
  opts = opts || {};
  const clock = opts.clock || (() => new Date());
  const hash = opts.passwordHash || '';
  if (hash && !validHash(hash)) throw new Error('CORE8_PILOT_PASSWORD_HASH is not a valid hash. Create one with: node tools/hash-password.cjs');
  const maxFailures = opts.maxFailures || 5;
  const lockMs = (opts.lockMinutes || 15) * 60000;
  const sessionMs = (opts.sessionHours || 12) * 3600000;
  const sessions = new Map();
  let failures = 0;
  let lockedUntil = 0;

  return {
    enabled: !!hash,
    login(password) {
      const now = clock().getTime();
      if (now < lockedUntil) return { ok: false, locked: true, retryAfterSeconds: Math.ceil((lockedUntil - now) / 1000) };
      if (!verifyPassword(password, hash)) {
        failures += 1;
        if (failures >= maxFailures) { lockedUntil = now + lockMs; failures = 0; }
        return { ok: false, locked: false };
      }
      failures = 0;
      const token = crypto.randomBytes(32).toString('base64url');
      sessions.set(token, now + sessionMs);
      return { ok: true, token, maxAgeSeconds: sessionMs / 1000 };
    },
    check(token) {
      if (!token || !sessions.has(token)) return false;
      if (sessions.get(token) <= clock().getTime()) { sessions.delete(token); return false; }
      return true;
    },
    logout(token) { sessions.delete(token); },
    sessionCount: () => sessions.size
  };
}

function readCookie(header, name) {
  for (const part of String(header || '').split(';')) {
    const i = part.indexOf('=');
    if (i !== -1 && part.slice(0, i).trim() === name) return part.slice(i + 1).trim();
  }
  return '';
}

module.exports = { hashPassword, verifyPassword, validHash, createAuth, readCookie };
