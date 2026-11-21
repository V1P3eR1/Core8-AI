# Core8-AI landing page — prototype

**Status: DRAFT FOR LEV'S REVIEW.** Not published, not connected to a domain,
not indexed (`noindex`). The copy is a proposal, not approved text.

A static, dependency-free page (Hebrew RTL first, English mirror) meant to
replace the current site, which runs on a third-party closed platform. Open
`index.html` directly, or add `?lang=en`.

## What it deliberately does not contain

- Prices, figures, percentages, "24/7", guarantees, client names or results
  (enforced by `tests/static.test.cjs`).
- Any phone number, tracking script, font or asset from another domain.
- A connected form. With `config.formEndpoint` empty (the default) the form
  validates and then says nothing was sent.

## Form handler for PHP hosting

`server/lead.php` receives the form and e-mails one signed `CORE8 LEAD v1`
message to the business mailbox. The lead-triage tool (`apps/lead-triage-pilot`,
PR #31) reads that format and verifies the signature.

To switch the form on, on the host only:

1. Copy `server/lead-config.example.php` to `server/lead-config.php` and fill in
   the mailbox, a sender address on your own domain, a long random `secret`,
   the site's exact origin, and the id of the approved consent wording.
2. In `content.js` set `formEndpoint: 'server/lead.php'` and the same
   `consentTextId`.
3. Give the same secret to the lead-triage tool as `CORE8_LEAD_SECRET`.

`lead-config.php` is git-ignored and must never be committed. The handler needs
PHP 8.1+, puts no visitor input in mail headers, keeps only keyed-hash rate-limit
counters, and logs nothing personal. It has been tested in dry-run mode only:
**no real e-mail has been sent through it**, and delivery from the actual host
(SPF/DKIM, spam folder) is unverified.

## Decisions needed before launch (Lev)

1. **Copy.** Lev chose the `docs/LEV_CORE8_BRAND_BRIEF.md` (PR #21) direction on
   2026-11-19: headline, supporting copy and primary CTA are used verbatim
   (enforced by a test). The other sections are still Claude's draft.
2. **Consent wording and privacy policy.** Drafts are in place (`form.consent`,
   `privacy.html`, `accessibility.html`); they need legal review and the
   bracketed items filled in.
3. **Form destination.** Lev chose e-mail to the business mailbox via
   `server/lead.php`. The platform's own endpoint (`docs/LAUNCH_READINESS.md`
   §9) remains the later option; the field names match it.
4. **Hosting and DNS** for the page itself, and who controls the domain today.
5. **Logo.** The page uses the proposed "Agents in orbit" mark
   (`docs/brand/logo-agents-in-orbit/`).
   It has not had a trademark or similarity check.
6. **Phone/WhatsApp number** once the new one is active. The page shows the
   business email only.

## Publishing (owner only)

Nothing in this repository publishes the site. The steps, in order:

1. `npm run package` writes a **preview** build to `out/site/`: draft banner
   on, search engines blocked. Safe to upload to a test address to look at it.
2. Before launch, complete what `npm run package:launch` lists. It refuses to
   build while any of these is open:
   - `formEndpoint` and `consentTextId` set in `content.js`;
   - every `[to complete]` placeholder in `privacy.html` and
     `accessibility.html` filled in, after legal review.
3. `npm run package:launch` writes the launch build: same files with the draft
   banners and the search-engine block removed.
4. Upload the **contents** of `out/site/` to the site's public folder on the
   host, create `server/lead-config.php` there (never in git), then send one
   test inquiry and confirm it arrives in the mailbox and not in spam.
5. Point the domain at the host only after step 4 works.

`privacy.html` and `accessibility.html` are drafts written by Claude. They
describe what the page actually does (no cookies, form data e-mailed to the
business mailbox, human approval of replies) but **have not been reviewed by a
lawyer or an accessibility consultant**.

## Tests

```
npm test               # 8 static checks, 6 PHP handler tests (skipped without php), 3 packaging tests
npm run test:browser   # 7 offline browser checks + 1 browser-to-PHP check; needs Playwright and Chrome
```

Last recorded run (2026-11-19, Node 22.23.5, Playwright 1.63.0, Chrome 153,
Linux): 17 of 17 and 8 of 8 passed (PHP 8.3.6). Screenshots: `docs/evidence/landing-prototype/`.
Not tested: Firefox, Safari, real phones, screen readers.
