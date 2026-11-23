# Core8-AI customer demos (offline, mock data)

Standalone demos for showing customers what a Core8-AI agent could do.
**Nothing here is a production route.** The folder has no dependency on
`apps/core8-platform/` or `apps/my-goddess-orchestra/`, calls no API, needs no
key and stores nothing.

| Demo | Folder | Status |
|---|---|---|
| AI receptionist for the fictional "Or Clinic" (HE/EN) | `receptionist/` | READY FOR REVIEW (P0, Issue #24) |
| Portfolio carousel, reel storyboard, draft `calendar.csv` | — | not started (P1) |
| Internal Agent Studio | — | not started (P1) |
| Real-estate and car-service variants | — | not started (P2) |

## Open the receptionist demo

**Option A — no tools at all.** Double-click `receptionist/index.html`. It runs
from `file://` with the network unplugged.

**Option B — local server** (Node 18+; binds to 127.0.0.1 only):

```
cd apps/customer-demos
node tests/serve.cjs            # http://127.0.0.1:4173/receptionist/
```

Add `?lang=he` to open in Hebrew. Use **Reset demo** between run-throughs.

## What it does, and what it does not

- Role-play a patient: free text or suggested replies, in Hebrew or English.
- The inquiry is classified by **local keyword rules** — a deterministic
  stand-in for the production model. The demo does not call any AI model.
- A booking request leads to three **hypothetical** slots generated from a
  fixture (next three Sun–Thu days). No calendar is read.
- Choosing a slot prepares a **draft** confirmation and a **local lead preview**.
  Nothing is booked, sent or saved; status fields say so (`NOT CREATED`,
  `NOT SENT`).
- "Send to human review", "Talk to a person", urgent/medical wording,
  change/cancel requests and two unclear messages all end in a **simulated**
  human handoff. Nobody is notified.
- Lead CSV/JSON and the draft confirmation TXT are built in the page and
  downloaded to the presenter's own device.
- State lives in the tab's memory. Reload or **Reset demo** wipes it. No
  cookies, no web storage.

A `Content-Security-Policy` meta tag (`default-src 'none'; connect-src 'none'`)
blocks any network connection even if code were changed by mistake.

## Tests

```
cd apps/customer-demos
npm test                 # engine + static scans, Node built-in runner, no install
npm run test:browser     # Playwright: file:// (offline) and 127.0.0.1
```

The browser test needs the `playwright` package and a Chromium/Chrome binary.
If they are not on the default paths:

```
PLAYWRIGHT_MODULE=/path/to/node_modules/playwright CHROME_PATH=/path/to/chrome npm run test:browser
```

Results of the last recorded run, the demo script and open items are in
[`docs/DEMO_HANDOFF.md`](../../docs/DEMO_HANDOFF.md).

## Files

```
receptionist/index.html   page shell, CSP, banner
receptionist/styles.css   Core8 cosmic theme, RTL/LTR via logical properties
receptionist/fixtures.js  invented clinic data and keyword rules
receptionist/i18n.js      Hebrew/English strings, slot formatting
receptionist/engine.js    conversation state machine, lead + CSV/JSON export (no I/O)
receptionist/app.js       DOM rendering and events
tests/engine.test.cjs     17 unit tests
tests/static.test.cjs     8 source scans (no network/storage APIs, no secrets, contrast)
tests/browser.smoke.cjs   18 browser checks x 2 modes, writes evidence screenshots
tests/serve.cjs           127.0.0.1 static server
```
