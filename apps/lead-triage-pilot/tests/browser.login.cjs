'use strict';
/*
 * Browser check for the sign-in flow (Playwright + Chrome): redirect to the
 * sign-in page, wrong password, right password, sign out. Local server only.
 *
 *   PLAYWRIGHT_MODULE=/path/to/playwright CHROME_PATH=/path/to/chrome node tests/browser.login.cjs
 */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { createApp } = require('../server.cjs');
const { hashPassword } = require('../lib/auth.cjs');
const { tmpDir } = require('./helpers.cjs');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const EVIDENCE = path.resolve(process.env.EVIDENCE_DIR || path.join(__dirname, '..', '..', '..', 'docs', 'evidence', 'lead-triage-pilot'));
const PASSWORD = 'browser test password';
const results = []; let failed = 0;
async function check(name, fn) {
  try { await fn(); results.push('PASS  ' + name); }
  catch (e) { failed += 1; results.push('FAIL  ' + name + '\n      ' + String(e.message).split('\n').join('\n      ')); }
}

(async () => {
  fs.mkdirSync(EVIDENCE, { recursive: true });
  const dataDir = tmpDir();
  const app = createApp({ dataDir, quiet: true, auth: { passwordHash: hashPassword(PASSWORD) } });
  const port = await app.listen(0);
  const origin = 'http://127.0.0.1:' + port;
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined, args: process.env.CI_NO_SANDBOX ? ['--no-sandbox'] : [] });
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const blocked = [];
  await context.route('**/*', (route) => {
    const u = route.request().url();
    if (u.startsWith(origin + '/')) return route.continue();
    blocked.push(u); return route.abort();
  });
  await context.addInitScript(() => localStorage.setItem('c8lang', 'en')); // assertions below use the English text
  const page = await context.newPage();
  const T = (id) => page.locator(`[data-testid="${id}"]`);

  await check('a visitor without a session lands on the sign-in page', async () => {
    await page.goto(origin + '/');
    await page.waitForURL(origin + '/login.html');
    assert.equal(await T('password').getAttribute('type'), 'password');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'password');
  });

  await check('a wrong password shows an error and stays on the page', async () => {
    await T('password').fill('definitely wrong');
    await T('login').click();
    await page.waitForFunction(() => /Wrong password/.test(document.querySelector('[data-testid="login-error"]').textContent));
    assert.equal(await T('password').inputValue(), '');
    assert.equal(page.url(), origin + '/login.html');
    await page.screenshot({ path: path.join(EVIDENCE, '05-login.jpg'), type: 'jpeg', quality: 80 });
  });

  await check('the right password opens the tool; the cookie is HttpOnly and invisible to scripts', async () => {
    await T('password').fill(PASSWORD);
    await page.keyboard.press('Enter');
    await page.waitForURL(origin + '/');
    await page.waitForFunction(() => /Audit log intact/.test(document.querySelector('[data-testid="chain"]').textContent));
    assert.equal(await T('logout').isVisible(), true);
    assert.equal(await page.evaluate(() => document.cookie), '');
    const c = (await context.cookies()).find((k) => k.name === 'c8s');
    assert.equal(c.httpOnly, true);
    assert.equal(c.sameSite, 'Strict');
  });

  await check('sign out returns to the sign-in page and the session is gone', async () => {
    await T('logout').click();
    await page.waitForURL(origin + '/login.html');
    const res = await page.request.get(origin + '/api/state');
    assert.equal(res.status(), 401);
  });

  await check('no request left the machine', async () => { assert.deepEqual(blocked, []); });

  await browser.close();
  await app.close();
  fs.rmSync(dataDir, { recursive: true, force: true });
  console.log(results.join('\n'));
  console.log(`\n${results.length - failed} passed, ${failed} failed, ${results.length} total`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
