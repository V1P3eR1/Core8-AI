// From repo root with Playwright and Chromium installed:
// node apps/customer-demos/tests/showcase.smoke.cjs /path/to/evidence
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const out = path.resolve(process.argv[2] || 'showcase-evidence');
  fs.mkdirSync(out, {recursive:true});
  const browser = await chromium.launch({executablePath:process.env.CHROME_PATH || undefined});
  try {
    const page = await browser.newPage({viewport:{width:390,height:844}, offline:true});
    await page.goto(pathToFileURL(path.resolve(__dirname,'../../../docs/customer-showcase/index.html')).href);
    await page.evaluate(() => document.fonts.ready);
    assert.equal(await page.locator('article').count(),5);
    assert.equal(await page.locator('article .en[lang=en][dir=ltr]').count(),5);
    assert.equal(await page.locator('html').getAttribute('dir'),'rtl');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),'horizontal overflow');
    await page.screenshot({path:path.join(out,'mobile-390.png'),fullPage:true});
    await page.emulateMedia({media:'print'});
    assert.equal(await page.locator('nav').isVisible(),false);
    const color = await page.locator('header p').first().evaluate(el => getComputedStyle(el).color);
    assert.equal(color,'rgb(34, 34, 34)');
    await page.pdf({path:path.join(out,'showcase-a4.pdf'),format:'A4',printBackground:true});
    console.log('Review mobile-390.png and showcase-a4.pdf in',out);
  } finally { await browser.close(); }
})().catch(err => { console.error(err); process.exitCode = 1; });
