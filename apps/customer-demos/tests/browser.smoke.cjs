'use strict';
/*
 * Browser smoke test for the receptionist demo (Playwright + Chromium/Chrome).
 *
 * Runs the same scenario twice:
 *   1. file://  with the browser context forced OFFLINE (no internet at all)
 *   2. http://127.0.0.1 via tests/serve.cjs, with every non-local request blocked
 *
 * Usage:
 *   node tests/browser.smoke.cjs
 * Environment:
 *   CHROME_PATH        path to a Chrome/Chromium binary (else Playwright's bundled one)
 *   PLAYWRIGHT_MODULE  path to the playwright package if it is not resolvable
 *   EVIDENCE_DIR       where screenshots are written (default docs/evidence/customer-demos-p0)
 */
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');
const { listen } = require('./serve.cjs');

const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const DEMO_DIR = path.resolve(__dirname, '..', 'receptionist');
const REPO = path.resolve(__dirname, '..', '..', '..');
const EVIDENCE = path.resolve(process.env.EVIDENCE_DIR || path.join(REPO, 'docs', 'evidence', 'customer-demos-p0'));
// Thursday 19 Nov 2026 10:00 in Asia/Jerusalem (UTC+2) keeps dates in screenshots stable.
const FIXED_TIME = new Date('2026-11-19T08:00:00Z');

const results = [];
let failed = 0;

async function check(name, fn) {
  try {
    await fn();
    results.push('PASS  ' + name);
  } catch (err) {
    failed += 1;
    results.push('FAIL  ' + name + '\n      ' + String(err && err.message ? err.message : err).split('\n').join('\n      '));
  }
}

// Slot labels wrap the time in invisible bidi isolates; drop them for matching.
const text = async (page, testid) =>
  (await page.locator(`[data-testid="${testid}"]`).innerText()).replace(/[\u2066\u2069]/g, '');
const choice = (page, id) => page.locator(`[data-choice="${id}"]`);

async function say(page, message) {
  await page.fill('[data-testid="chat-input"]', message);
  await page.keyboard.press('Enter');
}

async function runScenario(browser, mode, url, isLocal) {
  const tag = `[${mode}] `;
  const downloadsDir = fs.mkdtempSync(path.join(os.tmpdir(), 'core8-demo-dl-'));
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    timezoneId: 'Asia/Jerusalem',
    locale: 'en-GB',
    acceptDownloads: true,
    reducedMotion: 'reduce', // also keeps screenshots free of mid-animation frames
    offline: mode === 'file'
  });
  const requests = [];
  const blocked = [];
  const consoleProblems = [];
  context.on('request', (r) => requests.push(r.url()));
  await context.route('**/*', (route) => {
    const u = route.request().url();
    if (isLocal(u)) return route.continue();
    blocked.push(u);
    return route.abort();
  });
  const page = await context.newPage();
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') consoleProblems.push(m.type() + ': ' + m.text()); });
  page.on('pageerror', (e) => consoleProblems.push('pageerror: ' + e.message));
  await page.clock.install({ time: FIXED_TIME });
  // Evidence screenshots come from the offline file:// run; the http run repeats
  // the same assertions without writing duplicate images.
  const shot = (name) => (mode === 'file'
    ? page.screenshot({ path: path.join(EVIDENCE, `${name}.jpg`), type: 'jpeg', quality: 82, fullPage: true })
    : Promise.resolve());

  await check(tag + 'page opens and shows the persistent DEMO / SIMULATION banner', async () => {
    await page.goto(url);
    const banner = await text(page, 'demo-banner');
    assert.match(banner, /DEMO \/ SIMULATION/);
    assert.match(banner, /no messages sent/);
    assert.match(banner, /no bookings created/);
    assert.equal(await page.locator('.msg').count(), 1, 'greeting only');
    assert.match(await page.locator('.msg').first().innerText(), /fictional clinic/);
    await shot('01-start-en');
  });

  await check(tag + 'typed message is classified as a booking inquiry by local rules', async () => {
    await say(page, "Hi, I'd like to book an appointment");
    assert.equal(await page.locator('[data-testid="intent-panel"] [data-intent]').getAttribute('data-intent'), 'booking');
    assert.match(await text(page, 'intent-method'), /Local keyword rules/);
    assert.match(await text(page, 'intent-matched'), /book, appointment/);
  });

  await check(tag + 'intake collects visit type, fictional name and contact', async () => {
    await choice(page, 'service:general').click();
    await choice(page, 'name:sample').click();
    await choice(page, 'contact:sample').click();
  });

  await check(tag + 'exactly three slots are offered, each labelled hypothetical', async () => {
    const chips = page.locator('[data-choice^="slot:"]');
    assert.equal(await chips.count(), 3);
    assert.equal(await page.locator('[data-choice^="slot:"] .tag--sim').count(), 3);
    assert.equal(await page.locator('[data-testid="slots-panel"] .slots__item').count(), 3);
    assert.equal(await page.locator('[data-testid="slots-panel"] .slots__item .tag--sim').count(), 3);
    assert.match(await text(page, 'slots-panel'), /No real calendar was read/);
    await shot('02-slots-en');
  });

  await check(tag + 'slot selection produces a draft confirmation and a local lead preview', async () => {
    await choice(page, 'slot:slot-2').click();
    const last = await page.locator('.msg--agent').last().innerText();
    assert.match(last, /draft request/);
    assert.match(last, /Nothing was booked and nothing was sent/);
    assert.equal(await text(page, 'lead-id'), 'DEMO-0001');
    assert.equal(await text(page, 'lead-record-status'), 'DRAFT');
    assert.equal(await text(page, 'lead-name'), 'Dana Example');
    assert.equal(await text(page, 'lead-contact'), 'dana@example.invalid');
    assert.match(await text(page, 'lead-slot'), /Monday,? 23 November, 13:00 · hypothetical/);
    assert.equal(await text(page, 'lead-booking-status'), 'NOT CREATED');
    assert.equal(await text(page, 'lead-message-status'), 'NOT SENT');
    assert.equal(await text(page, 'lead-handoff-status'), 'Not requested');
    await shot('03-draft-and-lead-en');
  });

  await check(tag + 'draft files download locally: lead CSV (header + 1 row), JSON, confirmation TXT', async () => {
    const grab = async (kind) => {
      const [dl] = await Promise.all([page.waitForEvent('download'), page.click(`[data-download="${kind}"]`)]);
      const target = path.join(downloadsDir, dl.suggestedFilename());
      await dl.saveAs(target);
      return { name: dl.suggestedFilename(), body: fs.readFileSync(target, 'utf8') };
    };
    const csv = await grab('csv');
    assert.equal(csv.name, 'or-clinic-demo-lead-DRAFT.csv');
    const lines = csv.body.replace(/^﻿/, '').trim().split('\r\n');
    assert.equal(lines.length, 2, 'header + exactly one lead row');
    assert.match(lines[1], /^DEMO-0001,DRAFT,IN_MEMORY_ONLY,true,Or Clinic \(fictional\),Dana Example,dana@example\.invalid,booking,general,2026-11-23,13:00,true,NOT_CREATED,NOT_SENT,NOT_REQUESTED,,/);
    const json = JSON.parse((await grab('json')).body);
    assert.equal(json.lead.bookingStatus, 'NOT_CREATED');
    const txt = await grab('txt');
    assert.match(txt.body, /DRAFT CONFIRMATION — DEMO \/ SIMULATION/);
    assert.match(txt.body, /NOT sent to anyone/);
    assert.equal(await page.locator('[data-audit="audit.file_exported"]').count(), 3);
  });

  await check(tag + 'manual handoff is shown as simulated, with nobody notified', async () => {
    await choice(page, 'draft:handoff').click();
    assert.match(await page.locator('.msg--agent').last().innerText(), /nobody was actually notified/);
    assert.match(await text(page, 'lead-handoff-status'), /Simulated — pending human review \(nobody was notified\)/);
    assert.equal(await text(page, 'lead-booking-status'), 'NOT CREATED');
    assert.equal(await text(page, 'lead-message-status'), 'NOT SENT');
    assert.equal(await page.locator('[data-testid="stepper"] [data-done="true"]').count(), 6);
    assert.equal(await page.locator('[data-choice]').count(), 0, 'no further replies after handoff');
  });

  await check(tag + 'audit trail lists every step in order, all tagged simulated', async () => {
    const keys = await page.locator('[data-testid="audit-list"] [data-audit]').evaluateAll((n) => n.map((x) => x.getAttribute('data-audit')));
    const core = keys.filter((k) => !['audit.quick_reply', 'audit.file_exported', 'audit.message_received'].includes(k));
    assert.deepEqual(core, [
      'audit.session_started', 'audit.intent_classified_rules', 'audit.service_selected',
      'audit.name_captured', 'audit.contact_captured', 'audit.slots_generated', 'audit.slot_selected',
      'audit.draft_prepared', 'audit.lead_preview_created', 'audit.handoff_simulated'
    ]);
    assert.equal(await page.locator('[data-testid="audit-list"] .tag--sim').count(), keys.length);
    await shot('04-handoff-audit-en');
  });

  await check(tag + 'switching to Hebrew flips direction to RTL and translates labels and transcript', async () => {
    assert.equal(await page.getAttribute('html', 'dir'), 'ltr');
    await page.click('[data-lang="he"]');
    assert.equal(await page.getAttribute('html', 'dir'), 'rtl');
    assert.equal(await page.getAttribute('html', 'lang'), 'he');
    assert.equal(await page.evaluate(() => getComputedStyle(document.body).direction), 'rtl');
    assert.match(await text(page, 'demo-banner'), /הדגמה \/ סימולציה — לא נשלחות הודעות · לא נקבעים תורים/);
    assert.equal(await page.locator('h1').innerText(), 'פקידת קבלה AI למרפאה');
    assert.equal(await text(page, 'reset'), 'איפוס ההדגמה');
    assert.match(await page.locator('.msg').first().innerText(), /מרפאה בדיונית/);
    assert.equal(await text(page, 'lead-booking-status'), 'לא נקבע');
    assert.equal(await text(page, 'lead-message-status'), 'לא נשלחה');
    assert.equal(await page.getAttribute('[data-lang="he"]', 'aria-pressed'), 'true');
    // Agent bubbles sit on the inline-start side: the right edge in RTL.
    const log = await page.locator('[data-testid="chat-log"]').boundingBox();
    const bubble = await page.locator('.msg--agent').last().boundingBox();
    assert.ok(bubble.x + bubble.width > log.x + log.width - 40, 'agent bubble hugs the right edge in RTL');
    await shot('05-handoff-audit-he');
    await page.click('[data-lang="en"]');
    assert.equal(await page.getAttribute('html', 'dir'), 'ltr');
    assert.equal(await page.locator('h1').innerText(), 'AI receptionist for a clinic');
  });

  await check(tag + 'Reset demo clears the conversation, lead, slots and audit trail', async () => {
    await page.click('[data-testid="reset"]');
    assert.equal(await page.locator('.msg').count(), 1);
    assert.match(await text(page, 'lead-panel'), /A lead preview is created when/);
    assert.match(await text(page, 'slots-panel'), /Slots appear after a booking request/);
    assert.equal(await page.locator('[data-testid="audit-list"] li').count(), 1);
    assert.equal(await page.locator('[data-testid="stepper"] [data-done="true"]').count(), 0);
    assert.equal(await page.inputValue('[data-testid="chat-input"]'), '');
  });

  await check(tag + 'urgent Hebrew message escalates straight to a human with no slots offered', async () => {
    await page.click('[data-lang="he"]');
    await say(page, 'דחוף, כואב לי מאוד');
    assert.equal(await page.locator('[data-testid="intent-panel"] [data-intent]').getAttribute('data-intent'), 'urgent');
    const msgs = await page.locator('.msg--agent').allInnerTexts();
    assert.ok(msgs.some((m) => /אינני יכולה לתת ייעוץ רפואי/.test(m)), 'no medical advice');
    assert.ok(msgs.some((m) => /אף אחד לא קיבל הודעה בפועל/.test(m)), 'simulated handoff notice');
    assert.equal(await page.locator('[data-testid="slots-panel"] .slots__item').count(), 0);
    assert.equal(await page.locator('[data-testid="lead-panel"] [data-handoff]').getAttribute('data-handoff'), 'SIMULATED_PENDING_HUMAN_REVIEW');
    await shot('06-urgent-escalation-he');
    await page.click('[data-testid="reset"]');
    await page.click('[data-lang="en"]');
  });

  await check(tag + '"Talk to a person" and two unclear messages both escalate', async () => {
    await choice(page, 'handoff').click();
    assert.match(await text(page, 'lead-handoff-status'), /customer asked for a person/);
    await page.click('[data-testid="reset"]');
    await say(page, 'asdf');
    assert.equal(await page.locator('[data-testid="lead-panel"] [data-handoff]').count(), 0);
    await say(page, 'qwerty');
    assert.match(await text(page, 'lead-handoff-status'), /not understood after two attempts/);
    await page.click('[data-testid="reset"]');
  });

  await check(tag + 'typed text is rendered as text, never as markup', async () => {
    await say(page, '<img src=x onerror="window.__xss=1"><b>book</b> appointment');
    assert.equal(await page.evaluate(() => window.__xss), undefined);
    assert.equal(await page.locator('.msg img, .msg b').count(), 0);
    assert.match(await page.locator('.msg--user').last().innerText(), /<img src=x/);
    await page.click('[data-testid="reset"]');
  });

  await check(tag + 'keyboard only: skip link, Enter to send, Space on a suggested reply', async () => {
    await page.goto(url); // fresh load: the first Tab stop must be the skip link
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => document.activeElement.className), 'skip-link');
    await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'chat-input');
    await page.keyboard.type('opening hours?');
    await page.keyboard.press('Enter');
    assert.match(await page.locator('.msg--agent').last().innerText(), /08:00–19:00 \(fictional\)/);
    await page.locator('[data-choice="intent:booking"]').focus();
    await page.keyboard.press('Space');
    assert.equal(await page.locator('[data-choice^="service:"]').count(), 3);
    const outline = await page.evaluate(() => {
      const b = document.querySelector('[data-choice^="service:"]');
      b.focus();
      return document.activeElement === b;
    });
    assert.ok(outline);
    await page.click('[data-testid="reset"]');
  });

  await check(tag + 'mobile preview toggle and a 390px viewport: no horizontal overflow, banner stays visible', async () => {
    await page.click('[data-testid="mobile-toggle"]');
    assert.equal(await page.getAttribute('[data-testid="mobile-toggle"]', 'aria-pressed'), 'true');
    const frame = await page.locator('[data-testid="stage"]').boundingBox();
    assert.ok(frame.width <= 400, 'stage is phone width: ' + frame.width);
    await shot('07-mobile-preview-toggle-en');
    await page.click('[data-testid="mobile-toggle"]');

    await page.setViewportSize({ width: 390, height: 844 });
    for (const lng of ['en', 'he']) {
      await page.click(`[data-lang="${lng}"]`);
      await choice(page, 'intent:booking').click();
      await choice(page, 'service:followup').click();
      await choice(page, 'name:sample').click();
      await choice(page, 'contact:skip').click();
      await choice(page, 'slot:slot-1').click();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      assert.ok(overflow <= 0, `${lng}: horizontal overflow ${overflow}px`);
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      const banner = await page.locator('[data-testid="demo-banner"]').boundingBox();
      assert.ok(banner.y >= -1 && banner.y < 5, `${lng}: banner pinned to the top while scrolled (y=${banner.y})`);
      await page.evaluate(() => window.scrollTo(0, 0));
      await shot(`08-mobile-390-${lng}`);
      await page.click('[data-testid="reset"]');
    }
    await page.click('[data-lang="en"]');
    await page.setViewportSize({ width: 1440, height: 1000 });
  });

  await check(tag + 'nothing persisted: no cookies, no web storage; reload starts clean', async () => {
    await choice(page, 'intent:booking').click();
    const stored = await page.evaluate(() => {
      let ls = -1; let ss = -1;
      try { ls = window.localStorage.length; ss = window.sessionStorage.length; } catch (e) { /* storage unavailable is fine */ }
      return { ls, ss, cookie: document.cookie };
    });
    assert.ok(stored.ls <= 0 && stored.ss <= 0, JSON.stringify(stored));
    assert.equal(stored.cookie, '');
    assert.deepEqual(await context.cookies(), []);
    await page.reload();
    assert.equal(await page.locator('.msg').count(), 1);
    assert.equal(await page.locator('[data-testid="audit-list"] li').count(), 1);
  });

  await check(tag + '?lang=he opens directly in Hebrew RTL', async () => {
    await page.goto(url + '?lang=he');
    assert.equal(await page.getAttribute('html', 'dir'), 'rtl');
    assert.match(await page.title(), /סימולציה/);
  });

  await check(tag + 'no external network requests, no console errors or CSP violations', async () => {
    assert.deepEqual(blocked, [], 'requests that tried to leave the machine');
    const nonLocal = requests.filter((u) => !isLocal(u));
    assert.deepEqual(nonLocal, []);
    const names = [...new Set(requests.filter((u) => !u.startsWith('blob:')).map((u) => u.split('?')[0].split('/').pop() || 'index.html'))].sort();
    assert.deepEqual(names, ['app.js', 'engine.js', 'fixtures.js', 'i18n.js', 'index.html', 'styles.css']);
    assert.deepEqual(consoleProblems, []);
  });

  await context.close();
  fs.rmSync(downloadsDir, { recursive: true, force: true });
}

(async () => {
  fs.mkdirSync(EVIDENCE, { recursive: true });
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || undefined,
    args: process.env.CI_NO_SANDBOX ? ['--no-sandbox'] : []
  });
  console.log('Browser: ' + browser.browserType().name() + ' ' + browser.version());

  const fileUrl = pathToFileURL(path.join(DEMO_DIR, 'index.html')).href;
  const fileDir = pathToFileURL(DEMO_DIR).href + '/';
  await runScenario(browser, 'file', fileUrl, (u) => u.startsWith(fileDir) || u.startsWith('blob:') || u.startsWith('data:'));

  const server = await listen(0);
  const origin = 'http://127.0.0.1:' + server.address().port;
  await runScenario(browser, 'http', origin + '/receptionist/', (u) => u.startsWith(origin + '/receptionist/') || u.startsWith('blob:') || u.startsWith('data:'));
  server.close();
  await browser.close();

  console.log(results.join('\n'));
  console.log(`\n${results.length - failed} passed, ${failed} failed, ${results.length} total`);
  console.log('Screenshots: ' + path.relative(REPO, EVIDENCE));
  process.exit(failed ? 1 : 0);
})().catch((err) => { console.error(err); process.exit(2); });
