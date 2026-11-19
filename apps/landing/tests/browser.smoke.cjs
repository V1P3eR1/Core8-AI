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
    assert.equal(await page.locator('h1').innerText(), 'פחות עבודה חוזרת. יותר זמן לעסק שלך.');
    assert.match(await page.title(), /Core8-AI/);
    assert.match(await page.locator('[data-testid="mock"]').innerText(), /המחשה בלבד/);
    assert.equal(await page.locator('[data-i18n]:empty').count(), 0, 'no untranslated element');
    assert.equal(await page.locator('[data-testid="contact-email"]').innerText(), 'office.core8ai@gmail.com');
    assert.equal(await page.getAttribute('[data-testid="contact-email"]', 'href'), 'mailto:office.core8ai@gmail.com');
    assert.equal(await page.locator('a[href^="tel:"], a[href*="wa.me"]').count(), 0, 'no phone or WhatsApp link yet');
    await shot('01-desktop-he');
  });

  await check('English switch flips direction and every label', async () => {
    await page.click('[data-lang="en"]');
    assert.equal(await page.getAttribute('html', 'dir'), 'ltr');
    assert.equal(await page.locator('h1').innerText(), 'Less repetitive work. More time for your business.');
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

  // End to end with the PHP handler in dry-run mode: browser -> lead.php -> spooled message.
  const os = require('node:os');
  const { spawn, spawnSync } = require('node:child_process');
  if (spawnSync('php', ['-v']).status !== 0) {
    results.push('SKIP  form submits through server/lead.php (php is not installed)');
  } else {
    await check('with an endpoint configured, the form posts once to server/lead.php and a signed message is spooled', async () => {
      const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'core8-landing-e2e-'));
      const spool = path.join(dir, 'spool'); fs.mkdirSync(spool);
      const port = 20000 + Math.floor(Math.random() * 20000);
      const origin = 'http://127.0.0.1:' + port;
      const cfg = { to: 'leads@example.invalid', from: 'Core8-AI website <no-reply@example.invalid>', secret: 'e2e-secret-not-real', allowed_origins: [origin], consent_text_ids: ['he-v1'], spool_dir: spool, rate_limit_dir: dir };
      fs.writeFileSync(path.join(dir, 'cfg.php'), '<?php return json_decode(' + JSON.stringify(JSON.stringify(cfg)) + ', true);');
      const php = spawn('php', ['-S', '127.0.0.1:' + port, '-t', DIR], { env: Object.assign({}, process.env, { CORE8_LEAD_CONFIG: path.join(dir, 'cfg.php') }), stdio: 'ignore' });
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' });
      try {
        const live = []; const errs = [];
        await ctx.route('**/*', (route) => { const u = route.request().url(); live.push(route.request().method() + ' ' + u); return u.startsWith(origin + '/') ? route.continue() : route.abort(); });
        const p2 = await ctx.newPage();
        p2.on('pageerror', (e) => errs.push(e.message));
        for (let i = 0; i < 50; i++) { try { await p2.goto(origin + '/index.html'); break; } catch (e) { await new Promise((r) => setTimeout(r, 100)); } }
        await p2.evaluate(() => { window.Core8Landing.config.formEndpoint = 'server/lead.php'; window.Core8Landing.config.consentTextId = 'he-v1'; });
        await p2.fill('#f-name', 'דנה לדוגמה');
        await p2.fill('#f-email', 'dana@example.invalid');
        await p2.fill('#f-message', 'מעוניינים בשיחת אפיון');
        await p2.check('#f-consent');
        await p2.click('[data-testid="submit"]');
        await p2.waitForFunction(() => /הפנייה התקבלה/.test(document.querySelector('[data-testid="form-status"]').textContent), null, { timeout: 8000 });
        assert.equal(await p2.inputValue('#f-name'), '', 'form is cleared after sending');
        const posts = live.filter((l) => l.startsWith('POST '));
        assert.deepEqual(posts, ['POST ' + origin + '/server/lead.php']);
        assert.deepEqual(live.filter((l) => !l.includes(origin + '/')), [], 'no request left the site');
        const mails = fs.readdirSync(spool);
        assert.equal(mails.length, 1);
        assert.match(fs.readFileSync(path.join(spool, mails[0]), 'utf8'), /-----BEGIN CORE8 LEAD v1-----[\s\S]+sig: [0-9a-f]{64}/);
        assert.deepEqual(errs, []);
      } finally { await ctx.close(); php.kill(); fs.rmSync(dir, { recursive: true, force: true }); }
    });
  }

  await browser.close();
  console.log('Browser: chromium ' + browser.version());
  console.log(results.join('\n'));
  const skipped = results.filter((r) => r.startsWith('SKIP')).length;
  console.log(`\n${results.length - failed - skipped} passed, ${failed} failed, ${skipped} skipped, ${results.length} total`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
