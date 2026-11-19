'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { createApp } = require('../server.cjs');
const A = require('../lib/auth.cjs');
const { tmpDir, raw } = require('./helpers.cjs');

const PASSWORD = 'correct horse battery';
const HASH = A.hashPassword(PASSWORD);

test('password hashing: verifies, rejects wrong and malformed input, enforces length', () => {
  assert.equal(A.validHash(HASH), true);
  assert.equal(A.verifyPassword(PASSWORD, HASH), true);
  assert.equal(A.verifyPassword(PASSWORD + 'x', HASH), false);
  assert.equal(A.verifyPassword(PASSWORD, 'scrypt$1$1$1$bad$bad'), false);
  assert.equal(A.verifyPassword(PASSWORD, ''), false);
  assert.throws(() => A.hashPassword('short'), /12 characters/);
  assert.notEqual(A.hashPassword(PASSWORD), HASH, 'fresh salt each time');
  assert.throws(() => A.createAuth({ passwordHash: 'plain-text-password' }), /not a valid hash/);
});

test('lockout after five wrong passwords, released after fifteen minutes; sessions expire', () => {
  let now = new Date('2026-01-01T10:00:00Z').getTime();
  const auth = A.createAuth({ passwordHash: HASH, clock: () => new Date(now) });
  for (let i = 0; i < 5; i += 1) assert.deepEqual(auth.login('wrong password!'), { ok: false, locked: false });
  const locked = auth.login(PASSWORD);
  assert.equal(locked.ok, false, 'even the right password is refused while locked');
  assert.equal(locked.locked, true);
  assert.equal(locked.retryAfterSeconds, 900);
  now += 15 * 60000 + 1000;
  const ok = auth.login(PASSWORD);
  assert.equal(ok.ok, true);
  assert.equal(auth.check(ok.token), true);
  assert.equal(auth.check('nope'), false);
  now += 12 * 3600000 + 1000;
  assert.equal(auth.check(ok.token), false, 'session ends after twelve hours');
  assert.equal(auth.sessionCount(), 0);
});

test('refuses to start on a public host without a password', () => {
  assert.throws(() => createApp({ dataDir: tmpDir(), quiet: true, auth: { publicHost: 'agent.example.com' } }), /Refusing to run/);
});

test('refuses to listen beyond the machine unless public host and password are both set', () => {
  assert.throws(() => createApp({ dataDir: tmpDir(), quiet: true, bindHost: '0.0.0.0' }), /Refusing to listen/);
  assert.throws(() => createApp({ dataDir: tmpDir(), quiet: true, bindHost: '0.0.0.0', auth: { passwordHash: HASH } }), /Refusing to listen/);
  assert.throws(() => createApp({ dataDir: tmpDir(), quiet: true, bindHost: '10.0.0.5', auth: { publicHost: 'a.example.com', passwordHash: HASH } }), /must be/);
  assert.ok(createApp({ dataDir: tmpDir(), quiet: true, bindHost: '0.0.0.0', auth: { publicHost: 'a.example.com', passwordHash: HASH } }));
});

test('server mode: everything needs a session; login sets a hardened cookie; logout ends it', async () => {
  const app = createApp({ dataDir: tmpDir(), quiet: true, auth: { publicHost: 'agent.example.com', passwordHash: HASH } });
  const port = await app.listen(0);
  const H = { Host: 'agent.example.com' };
  const get = (p, headers) => raw(port, { path: p, headers: Object.assign({}, H, headers) });
  const post = (p, body, headers) => raw(port, { method: 'POST', path: p, body, headers: Object.assign({}, H, headers) });

  assert.equal((await get('/api/state')).status, 401);
  assert.equal((await post('/api/leads', { text: 'Hello there' })).status, 401);
  assert.equal((await post('/api/intake/email', { raw: 'x' })).status, 401);
  assert.equal((await post('/api/mailbox/check', {})).status, 401);
  const page = await get('/');
  assert.equal(page.status, 302);
  assert.equal(page.headers.location, '/login.html');
  assert.equal((await get('/app.js')).status, 302, 'the app script is not served to strangers');
  const login = await get('/login.html');
  assert.equal(login.status, 200);
  assert.match(login.headers['strict-transport-security'], /max-age=31536000/);
  assert.equal(login.headers['x-frame-options'], 'DENY');
  assert.equal((await get('/login.js')).status, 200);

  assert.equal((await post('/api/login', { password: 'wrong password!' })).status, 401);
  assert.equal((await post('/api/login', { password: PASSWORD }, { Origin: 'https://evil.example' })).status, 403);
  assert.equal((await raw(port, { path: '/login.html', headers: { Host: 'other.example.com' } })).status, 403);

  const ok = await post('/api/login', { password: PASSWORD }, { Origin: 'https://agent.example.com' });
  assert.equal(ok.status, 200);
  const setCookie = ok.headers['set-cookie'][0];
  assert.match(setCookie, /^c8s=[A-Za-z0-9_-]{43};/);
  for (const flag of ['HttpOnly', 'SameSite=Strict', 'Secure', 'Path=/', 'Max-Age=43200']) assert.ok(setCookie.includes(flag), flag);
  assert.ok(!ok.text.includes(setCookie.slice(4, 47)), 'token is not in the response body');
  const Cookie = setCookie.split(';')[0];

  const state = await get('/api/state', { Cookie });
  assert.equal(state.status, 200);
  assert.equal(state.json.config.loginRequired, true);
  assert.equal(state.json.config.publicHost, 'agent.example.com');
  assert.equal((await get('/', { Cookie })).status, 200);
  assert.equal((await get('/api/state', { Cookie: 'c8s=' + 'A'.repeat(43) })).status, 401, 'a guessed token is refused');

  const out = await post('/api/logout', {}, { Cookie });
  assert.match(out.headers['set-cookie'][0], /Max-Age=0/);
  assert.equal((await get('/api/state', { Cookie })).status, 401);
  await app.close();
});

test('server mode: five wrong passwords over HTTP give 429 with Retry-After', async () => {
  const app = createApp({ dataDir: tmpDir(), quiet: true, auth: { passwordHash: HASH } });
  const port = await app.listen(0);
  for (let i = 0; i < 5; i += 1) assert.equal((await raw(port, { method: 'POST', path: '/api/login', body: { password: 'wrong password!' } })).status, 401);
  const r = await raw(port, { method: 'POST', path: '/api/login', body: { password: PASSWORD } });
  assert.equal(r.status, 429);
  assert.ok(Number(r.headers['retry-after']) > 0);
  await app.close();
});

test('local mode without a password stays open and says so', async () => {
  const app = createApp({ dataDir: tmpDir(), quiet: true });
  const port = await app.listen(0);
  const s = await raw(port, { path: '/api/state' });
  assert.equal(s.status, 200);
  assert.equal(s.json.config.loginRequired, false);
  assert.equal(s.headers['strict-transport-security'], undefined);
  await app.close();
});

test('hash-file mode: starts locked, opens once the owner sets a password, follows a change without restart', async () => {
  const dir = tmpDir();
  const file = path.join(dir, 'password.hash');
  const app = createApp({ dataDir: tmpDir(), quiet: true, auth: { publicHost: 'agent.example.com', passwordHashFile: file } });
  const port = await app.listen(0);
  const H = { Host: 'agent.example.com' };
  const login = (password) => raw(port, { method: 'POST', path: '/api/login', body: { password }, headers: H });
  const setPw = (pw) => execFileSync(process.execPath, [path.join(__dirname, '..', 'tools', 'set-password.cjs')],
    { input: pw + '\n', env: Object.assign({}, process.env, { CORE8_PILOT_PASSWORD_HASH_FILE: file }), encoding: 'utf8' });

  assert.equal(app.auth.passwordSet(), false);
  assert.equal((await raw(port, { path: '/api/state', headers: H })).status, 401, 'locked, not open');
  assert.equal((await raw(port, { path: '/login.html', headers: H })).status, 200);
  for (let i = 0; i < 7; i += 1) assert.equal((await login(PASSWORD)).status, 503, 'no password works before one is set, and it does not trip the lockout');

  fs.writeFileSync(file, 'not a hash\n');
  assert.equal((await login(PASSWORD)).status, 503, 'a damaged file keeps it locked');

  assert.throws(() => setPw('short'), /12 characters/);
  assert.match(setPw(PASSWORD), /Password set/);
  assert.equal(fs.statSync(file).mode & 0o777, 0o600);
  assert.ok(!fs.readFileSync(file, 'utf8').includes(PASSWORD));
  assert.equal((await login('wrong password!')).status, 401);
  const ok = await login(PASSWORD);
  assert.equal(ok.status, 200);

  setPw('a different password');
  assert.equal((await login(PASSWORD)).status, 401, 'the old password stops working at once');
  assert.equal((await login('a different password')).status, 200);
  await app.close();
});
