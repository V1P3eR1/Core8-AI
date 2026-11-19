# Demo handoff — Sprint 01, P0 receptionist demo

**Status: READY FOR REVIEW.** Not merged, not deployed, not published. Acceptance
is a human decision; passing local tests does not establish it.

- Intake: Issue #24 · scope doc `docs/CUSTOMER_DEMO_SPRINT_01.md`
- Branch: `demo/p0-receptionist-or-clinic` → base `demo/customer-showcase-sprint-01`
- Draft PR: https://github.com/V1P3eR1/Core8-AI/pull/26
- Run date: 2026-11-19 (Asia/Jerusalem), Claude Code session started by Lev
- Delivered: **P0 only.** P1 and P2 are not started.

## What was built

A static, bilingual (Hebrew RTL / English LTR) role-play of an AI receptionist
for the fictional "Or Clinic", in a new isolated folder. No existing file was
modified.

| Path | Purpose |
|---|---|
| `apps/customer-demos/README.md` | How to open, what it does and does not do |
| `apps/customer-demos/package.json` | Test scripts only; no dependencies |
| `apps/customer-demos/receptionist/index.html` | Page shell, CSP, persistent banner |
| `apps/customer-demos/receptionist/styles.css` | Core8 cosmic theme, responsive, RTL/LTR |
| `apps/customer-demos/receptionist/fixtures.js` | Invented clinic data, keyword rules |
| `apps/customer-demos/receptionist/i18n.js` | HE/EN strings and slot formatting |
| `apps/customer-demos/receptionist/engine.js` | Conversation state machine, lead and exports (no I/O) |
| `apps/customer-demos/receptionist/app.js` | Rendering and events |
| `apps/customer-demos/tests/*.cjs` | Unit tests, static scans, browser smoke test, local server |
| `docs/evidence/customer-demos-p0/*.jpg` | 9 screenshots written by the browser test |
| `docs/DEMO_HANDOFF.md` | This file |

## Run it

1. **File open:** double-click `apps/customer-demos/receptionist/index.html`.
   Works with the network disconnected.
2. **Local server:** `cd apps/customer-demos && node tests/serve.cjs`, then open
   `http://127.0.0.1:4173/receptionist/` (`?lang=he` for Hebrew).

No install, build step, API key or account is involved.

## Demo script (about three minutes)

1. Point at the amber banner: demo / simulation, nothing sent, nothing booked,
   fictional clinic. It stays pinned while scrolling.
2. Type "Hi, I'd like to book an appointment". The *Inquiry classification*
   panel shows the intent and the keywords that matched. Say plainly that the
   demo uses keyword rules as a stand-in for the production model.
3. Pick a visit type, tap the fictional sample name and contact.
4. Three slots appear, each tagged *hypothetical*. Pick one.
5. The receptionist answers with a **draft** request. The *Lead preview* panel
   shows `DRAFT`, booking `NOT CREATED`, message `NOT SENT`.
6. Download the lead CSV and the draft confirmation — files generated in the
   browser, saved to the presenter's device.
7. Tap **Send to human review**. Handoff shows as *simulated — nobody was
   notified*. Walk down the audit trail.
8. Tap **עברית**: the whole page, including the conversation so far, flips to
   Hebrew RTL.
9. **Reset demo**, type "דחוף, כואב לי" to show the urgent path: no medical
   advice, no slots, straight to a human.
10. Optional: **Mobile preview** for the phone-width layout.

Suggested framing (from the sprint doc): "Core8-AI demonstrates how an AI
receptionist can handle inquiries and prepare a booking request, with escalation
to a human. The mockup uses fictitious availability; production integrations and
results require separate configuration and validation."

## Acceptance criteria and evidence

| Criterion (Issue #24 / sprint doc) | Result | Evidence |
|---|---|---|
| Opens offline, no credentials, no internet | Passed | Browser run 1 uses `file://` with the browser context set offline |
| Mock message → slot selection → draft confirmation → lead preview → manual handoff | Passed | Browser checks 2–8; screenshots 01–04 |
| Human escalation | Passed | Urgent (HE), "talk to a person", cancel, two unclear messages; screenshot 06 |
| Three explicitly hypothetical slots | Passed | Exactly 3 chips and 3 panel rows, each tagged; unit test over 14 start dates |
| HE RTL ↔ EN LTR changes labels and direction | Passed | `html[dir]`, computed direction, labels, transcript, bubble side; screenshot 05 |
| Persistent "DEMO / SIMULATION" banner | Passed | Banner text asserted in both languages; pinned at top while scrolled at 390 px |
| Local lead preview, downloadable draft files | Passed | CSV has header + exactly 1 row; JSON and TXT parsed |
| Step-by-step audit trail | Passed | Order asserted in unit and browser tests; every row tagged simulated |
| Reset demo | Passed | Conversation, lead, slots, audit and progress cleared |
| Responsive / mobile preview | Passed | 390×844 viewport in EN and HE, no horizontal overflow; screenshots 07–08 |
| Accessible navigation | Partly | Skip link, keyboard-only path, focus handling and AA contrast are tested. Not tested with a screen reader |
| No external network calls | Passed | Every request recorded; anything non-local is blocked and fails the run. CSP `connect-src 'none'`. Source scan for network APIs |
| No credentials, personal data or browser-shipped keys | Passed | Source scans for secret patterns, emails (only `example.invalid`), phone-like numbers |
| No ungrounded ROI / uptime claims | Passed | Copy scan; the demo shows no KPIs at all |
| Fake names and contacts only | Passed for shipped data | Sample persona "Dana Example", `dana@example.invalid`. A presenter can still type anything; the UI asks for made-up details and nothing leaves the tab |
| Portfolio 5 panels; `calendar.csv` 2 rows | Not started | P1 |
| Agent Studio; industry variants | Not started | P1 / P2 |

## Test commands and output

Environment: Node v22.23.5, Playwright 1.63.0, Chrome 153.0.8010.12, Linux.
Run from `apps/customer-demos/` on 2026-11-19.

### `npm test` — exit 0

```
ok 1 - classifies English and Hebrew inquiries
ok 2 - urgent outranks booking; keywords need a word start
ok 3 - generates exactly three hypothetical slots on upcoming working days
ok 4 - happy path with suggested replies ends in a draft, not a booking
ok 5 - happy path works with typed messages only
ok 6 - audit trail records each step in order
ok 7 - escalates urgent, human, cancel and repeatedly unclear inquiries
ok 8 - urgent message interrupts mid-booking; a typed name is not misread as an escalation
ok 9 - hours and pricing answers stay in the conversation and make no promises
ok 10 - picking another slot clears the draft until a new slot is chosen
ok 11 - invalid or out-of-step choices are ignored
ok 12 - input is trimmed, length-limited and stripped of control characters
ok 13 - lead CSV has a header and exactly one row, and neutralises formulas
ok 14 - draft confirmation text says it was not sent, in both languages
ok 15 - reset returns to a clean greeting with no carried-over data
ok 16 - Hebrew and English string tables have identical keys and no blanks
ok 17 - every suggested reply and bot message renders in both languages
ok 18 - demo folder contains only the expected static files
ok 19 - no remote URLs or protocol-relative references
ok 20 - no network, storage or dynamic-code APIs
ok 21 - page loads only its own local scripts and stylesheet under a strict CSP
ok 22 - no credential-shaped strings
ok 23 - only reserved, non-routable sample contact data
ok 24 - simulation wording is present in both languages and no outcome claims are made
ok 25 - text colours meet WCAG AA contrast on their backgrounds
# tests 25
# pass 25
# fail 0
# skipped 0
```

### `npm run test:browser` — exit 0

Run with `PLAYWRIGHT_MODULE` and `CHROME_PATH` pointing at the local install.
Dates in screenshots are fixed to Thu 19 Nov 2026 10:00 Asia/Jerusalem.

```
Browser: chromium 153.0.8010.12
PASS  [file] page opens and shows the persistent DEMO / SIMULATION banner
PASS  [file] typed message is classified as a booking inquiry by local rules
PASS  [file] intake collects visit type, fictional name and contact
PASS  [file] exactly three slots are offered, each labelled hypothetical
PASS  [file] slot selection produces a draft confirmation and a local lead preview
PASS  [file] draft files download locally: lead CSV (header + 1 row), JSON, confirmation TXT
PASS  [file] manual handoff is shown as simulated, with nobody notified
PASS  [file] audit trail lists every step in order, all tagged simulated
PASS  [file] switching to Hebrew flips direction to RTL and translates labels and transcript
PASS  [file] Reset demo clears the conversation, lead, slots and audit trail
PASS  [file] urgent Hebrew message escalates straight to a human with no slots offered
PASS  [file] "Talk to a person" and two unclear messages both escalate
PASS  [file] typed text is rendered as text, never as markup
PASS  [file] keyboard only: skip link, Enter to send, Space on a suggested reply
PASS  [file] mobile preview toggle and a 390px viewport: no horizontal overflow, banner stays visible
PASS  [file] nothing persisted: no cookies, no web storage; reload starts clean
PASS  [file] ?lang=he opens directly in Hebrew RTL
PASS  [file] no external network requests, no console errors or CSP violations
PASS  [http] page opens and shows the persistent DEMO / SIMULATION banner
PASS  [http] typed message is classified as a booking inquiry by local rules
PASS  [http] intake collects visit type, fictional name and contact
PASS  [http] exactly three slots are offered, each labelled hypothetical
PASS  [http] slot selection produces a draft confirmation and a local lead preview
PASS  [http] draft files download locally: lead CSV (header + 1 row), JSON, confirmation TXT
PASS  [http] manual handoff is shown as simulated, with nobody notified
PASS  [http] audit trail lists every step in order, all tagged simulated
PASS  [http] switching to Hebrew flips direction to RTL and translates labels and transcript
PASS  [http] Reset demo clears the conversation, lead, slots and audit trail
PASS  [http] urgent Hebrew message escalates straight to a human with no slots offered
PASS  [http] "Talk to a person" and two unclear messages both escalate
PASS  [http] typed text is rendered as text, never as markup
PASS  [http] keyboard only: skip link, Enter to send, Space on a suggested reply
PASS  [http] mobile preview toggle and a 390px viewport: no horizontal overflow, banner stays visible
PASS  [http] nothing persisted: no cookies, no web storage; reload starts clean
PASS  [http] ?lang=he opens directly in Hebrew RTL
PASS  [http] no external network requests, no console errors or CSP violations

36 passed, 0 failed, 36 total
Screenshots: docs/evidence/customer-demos-p0
```

### Existing repository tests — unchanged

`python -m unittest discover -s tools/handoff -p 'test_*.py'` → `Ran 28 tests … OK`.
Backend tests under `apps/core8-platform/backend` were not run: no backend file
changed and they need the backend's dependencies.

### Screenshots

`docs/evidence/customer-demos-p0/`: `01-start-en`, `02-slots-en`,
`03-draft-and-lead-en`, `04-handoff-audit-en`, `05-handoff-audit-he`,
`06-urgent-escalation-he`, `07-mobile-preview-toggle-en`, `08-mobile-390-en`,
`08-mobile-390-he`. They are regenerated on every browser test run.

## Checks skipped, with reasons

- **Independent review (catalog capability 07, Codex):** skipped — no separate
  reviewer session available here. The diff has had no second reviewer.
- **gitleaks / secret-scan workflow:** not run locally; the repository workflow
  runs on the pull request.
- **Firefox, Safari, iOS, a physical phone:** not tested. Chrome on Linux only.
- **Screen reader (NVDA / VoiceOver / TalkBack):** not tested.
- **Hebrew copy review by a native speaker:** not done. I wrote the Hebrew.
- **The ChatGPT ZIP prototype:** not in the repository, not seen, not used.

## Caveats a reviewer should know

1. **The classifier is keyword rules, not a model.** It is labelled as such in
   the UI and audit trail. The demo shows the workflow, not answer quality. It
   will misread phrasings outside its word list ("unclear" twice → human).
2. **Slot dates move with the presenter's clock** (next three Sun–Thu days).
   Times are fixed at 09:30, 13:00, 17:15.
3. **"Or Clinic" / "מרפאת אור" is a common name.** It came from the sprint doc.
   The UI marks it fictional everywhere, but nobody has checked for a real
   clinic with that name. Lev's call before it is shown to customers.
4. **Downloads are real files** on the presenter's device, with `DRAFT` in the
   filename. If a presenter types real details, they end up in those files.
5. **No CI job runs these tests.** Adding one means editing workflow files,
   which `CLAUDE.md` reserves for a separate reviewed PR.
6. **Process note:** this work was started by Lev's direct instruction in a
   Claude Code session with shell access, not through the hash-approved Actions
   lane in `docs/HANDOFF.md`. Notion was not read or updated.

## Agent team (PR #23) — how it was used

PR #23 is merged on `main` (`12e0520`) and defines five department agents
(`core8-build`, `core8-design`, `core8-grow`, `core8-make`, `core8-run`), the
`core8-team` router skill and a 42-row capability catalog.

- This work followed the `core8-build` and `core8-design` steps as written in
  `.claude/skills/` on `main`. The two skills did not load in this session, so
  they were applied by reading them, not invoked.
- Capabilities exercised: **04** GitHub CLI (REST via `gh api`), **06**
  Playwright, **41** Node.js. Not used: **05** Vercel (no deployment in scope),
  **07** Codex review (unavailable).
- Handoff format follows `docs/core8-agents/README.md`: each check is reported
  as passed, failed or skipped with a reason.

For the P1 Agent Studio, three things need a decision before building:

- **The sprint branch predates PR #23.** `demo/customer-showcase-sprint-01` was
  cut from `d26972d`; `docs/core8-agents/` and `.claude/` are not on it. It needs
  `main` merged in (Lev's action) before the Studio can link to those files.
- **Two different sets of "five agents" exist.** `docs/AGENTS_CATALOG.md` lists
  the platform's seeded runtime agents (`general`, `leads`, `calendar`, `design`,
  `instagram`). PR #23 adds five department agents for coding sessions. Issue #24
  says not to replace the seeded IDs; the Studio should show both sets as
  separate record types. PR #23 itself notes the two catalogs were not reconciled.
- **Catalog 01–42 now has a source file, but not verification.** Each row names
  an external tool with prerequisites. Whether any of them is installed or
  authorised is unknown, so Issue #24's instruction to treat them as unverified
  still holds.

## Still open

- P1: portfolio carousel (5 panels), reel storyboard, `calendar.csv` (2 draft
  rows), internal Agent Studio.
- P2: real-estate and car-service variants.
- Review of customer messaging and acceptance (ChatGPT lane); merge decision (Lev).
- Launch blockers #11 (privilege concerns) and #7 (tenant isolation) are
  untouched by this work and still block public production onboarding.
