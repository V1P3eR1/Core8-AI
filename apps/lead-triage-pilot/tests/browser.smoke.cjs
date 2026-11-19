'use strict';
/*
 * Browser smoke test for the lead-triage pilot UI (Playwright + Chrome).
 * Starts the real server on a random loopback port with a temporary data
 * folder and the offline rules engine, and fails on any non-local request.
 *
 *   PLAYWRIGHT_MODULE=/path/to/playwright CHROME_PATH=/path/to/chrome node tests/browser.smoke.cjs
 */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { createApp } = require('../server.cjs');
const { tmpDir } = require('./helpers.cjs');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const REPO = path.resolve(__dirname, '..', '..', '..');
const EVIDENCE = path.resolve(process.env.EVIDENCE_DIR || path.join(REPO, 'docs', 'evidence', 'lead-triage-pilot'));
const results = []; let failed = 0;
async function check(name, fn) {
  try { await fn(); results.push('PASS  ' + name); }
  catch (e) { failed += 1; results.push('FAIL  ' + name + '\n      ' + String(e.message).split('\n').join('\n      ')); }
}
const T = (page, id) => page.locator(`[data-testid="${id}"]`);
// The UI updates after a round trip to the local server, so wait for the text.
const waitText = (page, selector, pattern) => page.waitForFunction(
  ([sel, src]) => { const n = document.querySelector(sel); return !!n && new RegExp(src).test(n.textContent); },
  [selector, pattern.source], { timeout: 5000 });
const waitId = (page, id, pattern) => waitText(page, `[data-testid="${id}"]`, pattern);

(async () => {
  fs.mkdirSync(EVIDENCE, { recursive: true });
  const dataDir = tmpDir();
  const app = createApp({ dataDir, quiet: true });
  const port = await app.listen(0);
  const origin = 'http://127.0.0.1:' + port;
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined, args: process.env.CI_NO_SANDBOX ? ['--no-sandbox'] : [] });
  const context = await browser.newContext({ viewport: { width: 1360, height: 950 }, acceptDownloads: true, reducedMotion: 'reduce', timezoneId: 'Asia/Jerusalem' });
  const blocked = []; const problems = [];
  await context.route('**/*', (route) => {
    const u = route.request().url();
    if (u.startsWith(origin + '/') || u.startsWith('blob:')) return route.continue();
    blocked.push(u); return route.abort();
  });
  const page = await context.newPage();
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') problems.push(m.text()); });
  page.on('pageerror', (e) => problems.push('pageerror: ' + e.message));
  const shot = (n) => page.screenshot({ path: path.join(EVIDENCE, n + '.jpg'), type: 'jpeg', quality: 82, fullPage: true });
  const add = async (text, channel, label) => {
    await T(page, 'f-text').fill(text);
    if (channel) await T(page, 'f-channel').selectOption(channel);
    if (label) await T(page, 'f-label').fill(label);
    const before = app.store.leads().length;
    await T(page, 'add').click();
    await waitId(page, 'd-id', new RegExp('L-000' + (before + 1)));
  };

  await check('opens with the drafts-only banner, offline engine and an intact empty log', async () => {
    await page.goto(origin + '/');
    await waitId(page, 'chain', /Audit log intact/);
    assert.match(await T(page, 'banner').innerText(), /PILOT · DRAFTS ONLY/);
    assert.match(await T(page, 'banner').innerText(), /cannot send anything/);
    assert.equal(await T(page, 'engine').getAttribute('data-engine'), 'rules');
    assert.match(await T(page, 'engine').innerText(), /nothing leaves this computer/);
    assert.match(await T(page, 'chain').innerText(), /Audit log intact · 0 events/);
    assert.equal(await page.locator('[data-metric="leads"] .metric__value').innerText(), '0');
  });

  await check('a Hebrew inquiry is classified and gets a Hebrew draft with a placeholder warning', async () => {
    await add('שלום, כמה עולה סוכן AI לעסק שלי? דחוף', 'whatsapp', 'Sample lead A');
    assert.equal(await T(page, 'd-id').innerText(), 'L-0001');
    assert.equal(await T(page, 'd-status').innerText(), 'Needs review');
    assert.equal(await T(page, 'd-category').innerText(), 'Pricing');
    assert.equal(await T(page, 'd-urgency').innerText(), 'high');
    assert.equal(await T(page, 'd-engine').innerText(), 'Offline rules');
    assert.match(await T(page, 'd-draft').inputValue(), /תודה על ההתעניינות/);
    assert.match(await T(page, 'd-flags').innerText(), /placeholder to fill in/);
    await shot('01-needs-review');
  });

  await check('an untouched template cannot be approved; an edited reply can', async () => {
    await page.click('[data-act="approve"]');
    await waitText(page, '#d-error', /placeholder/);
    assert.equal(await T(page, 'd-status').innerText(), 'Needs review');
    await T(page, 'd-draft').fill('שלום דנה, תודה על הפנייה. אפשר לתאם שיחה קצרה מחר?');
    await page.click('[data-act="approve"]');
    await waitId(page, 'd-status', /Approved — not sent/);
    assert.match(await T(page, 'd-decision').innerText(), /Approved after your edits/);
    assert.equal(await T(page, 'd-draft').getAttribute('readonly'), '');
    assert.equal(await page.locator('[data-act="approve"]').count(), 0);
  });

  await check('"sent" is only ever a human confirmation', async () => {
    await page.click('[data-act="sent"]');
    await waitId(page, 'd-status', /Sent by you/);
    assert.match(await T(page, 'd-sent').innerText(), /You marked this as sent/);
    assert.deepEqual(app.store.events().map((e) => e.type), ['lead_added', 'triage_completed', 'decision_recorded', 'marked_sent']);
  });

  await check('reject requires a reason; draft-again adds an audit event', async () => {
    await add('We offer SEO services and backlink packages', 'email');
    assert.equal(await T(page, 'd-category').innerText(), 'Not a lead');
    await page.click('[data-act="retriage"]');
    await page.waitForFunction(() => /7 events/.test(document.querySelector('[data-testid="chain"]').textContent));
    await page.click('[data-act="reject"]');
    await waitText(page, '#d-error', /reason is required/);
    await T(page, 'd-reason').fill('Vendor spam');
    await page.click('[data-act="reject"]');
    await waitId(page, 'd-status', /Rejected/);
    assert.match(await T(page, 'd-decision').innerText(), /Vendor spam/);
  });

  await check('inquiry text is shown as text, never run as markup', async () => {
    await add('<img src=x onerror="window.__xss=1"> can I get a <b>demo</b>?', 'website_form');
    assert.equal(await page.evaluate(() => window.__xss), undefined);
    assert.equal(await page.locator('[data-testid="detail"] img, [data-testid="queue"] img').count(), 0);
    assert.match(await T(page, 'd-text').innerText(), /<img src=x/);
    assert.equal(await T(page, 'd-category').innerText(), 'Demo / meeting');
  });

  await check('metrics, queue filters and audit status reflect the log', async () => {
    assert.equal(await page.locator('[data-metric="leads"] .metric__value').innerText(), '3');
    assert.equal(await page.locator('[data-metric="awaiting"] .metric__value').innerText(), '1');
    assert.equal(await page.locator('[data-metric="edited"] .metric__value').innerText(), '50%');
    assert.equal(await page.locator('[data-metric="rejected"] .metric__value').innerText(), '50%');
    assert.equal(await page.locator('[data-metric="asis"] .metric__value').innerText(), '0%');
    await page.click('[data-filter="all"]');
    assert.equal(await page.locator('[data-testid="queue"] [data-lead]').count(), 3);
    await page.click('[data-filter="sent"]');
    assert.equal(await page.locator('[data-testid="queue"] [data-lead]').count(), 1);
    await page.click('[data-filter="all"]');
    assert.match(await T(page, 'chain').innerText(), /Audit log intact · 10 events/);
    await shot('02-queue-and-metrics');
  });

  await check('evidence report downloads, verifies and contains no inquiry text', async () => {
    const [dl] = await Promise.all([page.waitForEvent('download'), T(page, 'report').click()]);
    assert.match(dl.suggestedFilename(), /^core8-lead-pilot-evidence-\d{4}-\d{2}-\d{2}\.json$/);
    const file = path.join(dataDir, 'report.json');
    await dl.saveAs(file);
    const text = fs.readFileSync(file, 'utf8');
    const report = JSON.parse(text);
    assert.equal(report.integrity.ok, true);
    assert.equal(report.events.length, 10);
    assert.equal(report.metrics.leads, 3);
    assert.ok(!/דנה|סוכן|SEO|Sample lead|Vendor spam|demo<|img/.test(text), 'redacted');
  });

  await check('a pasted website-form e-mail becomes a lead with contact, consent, source and meeting suggestions', async () => {
    const { encodeLeadEmail } = require('../lib/intake.cjs');
    const mail = encodeLeadEmail({ v: 1, id: 'abcdef0123456789', submitted_at: new Date(Date.now() - 120000).toISOString(), form: 'landing', lang: 'he',
      name: 'דנה לדוגמה', company: 'חברה לדוגמה', email: 'dana@example.invalid', phone: '', message: 'נשמח לשיחת אפיון על אוטומציה של פניות', consent: true, consent_text_id: 'he-v1' }, '').body;
    assert.match(await T(page, 'intake-mode').innerText(), /unsigned e-mails are accepted/);
    await T(page, 'i-raw').fill('not a lead e-mail');
    await T(page, 'intake').click();
    await waitId(page, 'intake-error', /No CORE8 LEAD v1 block/);
    await T(page, 'i-raw').fill(mail);
    await T(page, 'intake').click();
    await waitId(page, 'd-id', /L-0004/);
    assert.equal(await T(page, 'd-name').innerText(), 'דנה לדוגמה');
    assert.equal(await T(page, 'd-email').innerText(), 'dana@example.invalid');
    assert.match(await T(page, 'd-consent').innerText(), /Given \(text he-v1\)/);
    assert.match(await T(page, 'd-source').innerText(), /Website form — unsigned/);
    assert.equal(await page.locator('[data-testid="d-slots"] li').count(), 3);
    const before = await T(page, 'd-draft').inputValue();
    await page.locator('[data-act="slot"]').first().click();
    const after = await T(page, 'd-draft').inputValue();
    assert.ok(after.length > before.length && /\d{2}:\d{2}$/.test(after), 'slot text appended to the draft');
    await T(page, 'i-raw').fill(mail);
    await T(page, 'intake').click();
    await waitId(page, 'intake-error', /already imported/);
    await shot('04-form-lead-with-slots');
  });

  await check('leads table lists every lead and exports a CSV with contact details', async () => {
    assert.equal(await page.locator('[data-testid="crm"] tbody tr').count(), 4);
    assert.match(await page.locator('[data-row="L-0004"]').innerText(), /דנה לדוגמה[\s\S]*חברה לדוגמה[\s\S]*dana@example\.invalid[\s\S]*Website form/);
    const [dl] = await Promise.all([page.waitForEvent('download'), T(page, 'crm-csv').click()]);
    const file = path.join(dataDir, 'crm.csv');
    await dl.saveAs(file);
    const lines = fs.readFileSync(file, 'utf8').replace(/^\ufeff/, '').trim().split('\r\n');
    assert.equal(lines.length, 5, 'header + 4 leads');
    assert.match(lines[0], /^ref,received_at,name,business,email,phone,/);
    assert.ok(lines.some((l) => l.startsWith('L-0004,') && l.includes('dana@example.invalid') && l.includes('he-v1')));
    await page.locator('[data-open="L-0001"]').click();
    assert.equal(await T(page, 'd-id').innerText(), 'L-0001');
  });

  await check('state survives a reload (it lives in the local log, not the browser)', async () => {
    await page.reload();
    await waitText(page, '[data-metric="leads"] .metric__value', /4/);
    assert.equal(await page.locator('[data-metric="leads"] .metric__value').innerText(), '4');
    assert.deepEqual(await context.cookies(), []);
    assert.equal(await page.evaluate(() => window.localStorage.length + window.sessionStorage.length), 0);
  });

  await check('usable at 390px wide with no horizontal overflow', async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.click('[data-filter="all"]');
    await page.locator('[data-lead="L-0003"]').click();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    assert.ok(overflow <= 0, 'overflow ' + overflow + 'px');
    await shot('03-mobile-390');
  });

  await check('no request left the machine; no console errors or CSP violations', async () => {
    assert.deepEqual(blocked, []);
    // The two deliberate invalid actions above each log one HTTP 400 in the console.
    const unexpected = problems.filter((p) => !/status of 4(00|22)/.test(p));
    assert.deepEqual(unexpected, []);
    const unprocessable = problems.filter((p) => /status of 422/.test(p));
    assert.equal(problems.filter((p) => /status of 400/.test(p)).length, 2, 'exactly the two expected 400s');
    assert.equal(unprocessable.length, 1, 'exactly the one expected 422');
  });

  await browser.close();
  await app.close();
  fs.rmSync(dataDir, { recursive: true, force: true });
  console.log('Browser: chromium ' + browser.version());
  console.log(results.join('\n'));
  console.log(`\n${results.length - failed} passed, ${failed} failed, ${results.length} total`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
