'use strict';
/* Browser smoke test for the landing prototype. Opens the page from disk with the browser offline. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const DIR = path.resolve(__dirname, '..');
const REPO = path.resolve(DIR, '..', '..');
const EVIDENCE = path.resolve(process.env.EVIDENCE_DIR || path.join(REPO, 'docs', 'evidence', 'landing-prototype'));
const results = []; let failed = 0;
async function check(name, fn) { try { await fn(); results.push('PASS  ' + name); } catch (e) { failed += 1; results.push('FAIL  ' + name + '\n      ' + String(e.message).split('\n').join('\n      ')); } }

(async () => {
  fs.mkdirSync(EVIDENCE, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined, args: process.env.CI_NO_SANDBOX ? ['--no-sandbox'] : [] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, offline: true, reducedMotion: 'reduce' });
  const base = pathToFileURL(DIR).href + '/';
  const requests = []; const problems = [];
  context.on('request', (r) => requests.push(r.url()));
  const page = await context.newPage();
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') problems.push(m.text()); });
  page.on('pageerror', (e) => problems.push('pageerror: ' + e.message));
  const url = base + 'index.html';
  const shot = (n) => page.screenshot({ path: path.join(EVIDENCE, n + '.jpg'), type: 'jpeg', quality: 80, fullPage: true });
  const status = () => page.locator('[data-testid="form-status"]').innerText();

  await check('opens in Hebrew RTL with the draft banner and a single H1', async () => {
    await page.goto(url);
    assert.equal(await page.getAttribute('html', 'dir'), 'rtl');
    assert.equal(await page.getAttribute('html', 'lang'), 'he');
    assert.match(await page.locator('[data-testid="draft-banner"]').innerText(), /טיוטת אב-טיפוס לאישור/);
    assert.equal(await page.locator('h1').count(), 1);
    assert.equal(await page.locator('h1').innerText(), 'סוכני AI שעובדים בשבילך. אתה מאשר כל החלטה.');
    assert.match(await page.title(), /Core8-AI/);
    assert.match(await page.locator('[data-testid="mock"]').innerText(), /המחשה בלבד/);
    assert.equal(await page.locator('[data-i18n]:empty').count(), 0, 'no untranslated element');
    await shot('01-desktop-he');
  });

  await check('English switch flips direction and every label', async () => {
    await page.click('[data-lang="en"]');
    assert.equal(await page.getAttribute('html', 'dir'), 'ltr');
    assert.equal(await page.locator('h1').innerText(), 'AI agents that do the work. You approve every decision.');
    assert.match(await page.locator('[data-testid="price-note"]').innerText(), /no price list/);
    assert.equal(await page.getAttribute('[data-lang="en"]', 'aria-pressed'), 'true');
    assert.equal(await page.locator('[data-i18n]:empty').count(), 0);
    await shot('02-desktop-en');
    await page.click('[data-lang="he"]');
  });

  await check('form validates name, contact and consent, then reports preview mode without sending', async () => {
    await page.click('[data-testid="submit"]');
    assert.equal(await status(), 'נא למלא שם.');
    await page.fill('#f-name', 'דנה לדוגמה');
    await page.click('[data-testid="submit"]');
    assert.equal(await status(), 'נא למלא אימייל או טלפון תקינים.');
    await page.fill('#f-email', 'not-an-email');
    await page.click('[data-testid="submit"]');
    assert.equal(await status(), 'נא למלא אימייל או טלפון תקינים.');
    assert.equal(await page.getAttribute('#f-email', 'aria-invalid'), 'true');
    await page.fill('#f-email', 'dana@example.invalid');
    await page.click('[data-testid="submit"]');
    assert.equal(await status(), 'נדרשת הסכמה כדי לשלוח.');
    await page.check('#f-consent');
    const before = requests.length;
    await page.click('[data-testid="submit"]');
    assert.match(await status(), /הטופס עדיין לא מחובר, ושום דבר לא נשלח/);
    assert.equal(requests.length, before, 'submitting made no request');
    await page.click('[data-lang="en"]');
    assert.match(await status(), /nothing was sent/);
    await page.click('[data-lang="he"]');
  });

  await check('keyboard: first Tab reaches the skip link; honeypot is not focusable', async () => {
    await page.goto(url);
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => document.activeElement.className), 'skip');
    assert.equal(await page.getAttribute('#f-website', 'tabindex'), '-1');
    const box = await page.locator('.hp').boundingBox();
    assert.ok(box.width <= 1 && box.height <= 1, 'honeypot wrapper is clipped to nothing');
    assert.equal(await page.getAttribute('.hp', 'aria-hidden'), 'true');
  });

  await check('390px wide: no horizontal overflow in either language', async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    for (const l of ['he', 'en']) {
      await page.click(`[data-lang="${l}"]`);
      const o = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      assert.ok(o <= 0, `${l} overflow ${o}px`);
    }
    await page.click('[data-lang="he"]');
    await shot('03-mobile-he');
  });

  await check('only local files were requested; no console errors or CSP violations; nothing stored', async () => {
    assert.deepEqual(requests.filter((u) => !u.startsWith(base)), []);
    assert.deepEqual(problems, []);
    assert.deepEqual(await context.cookies(), []);
  });

  await browser.close();
  console.log('Browser: chromium ' + browser.version());
  console.log(results.join('\n'));
  console.log(`\n${results.length - failed} passed, ${failed} failed, ${results.length} total`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
