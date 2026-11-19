# Core8-AI landing page — prototype

**Status: DRAFT FOR LEV'S REVIEW.** Not published, not connected to a domain,
not indexed (`noindex`). The copy is a proposal, not approved text.

A static, dependency-free page (Hebrew RTL first, English mirror) meant to
replace the current site, which runs on a third-party closed platform. Open
`index.html` directly, or add `?lang=en`.

## What it deliberately does not contain

- Prices, figures, percentages, "24/7", guarantees, client names or results
  (enforced by `tests/static.test.cjs`).
- Any contact detail, tracking script, font or asset from another domain.
- A working form. With `config.formEndpoint` empty the form validates and then
  says nothing was sent. There is no network code in the page.

## Decisions needed before launch (Lev)

1. **Copy and positioning.** This draft leads with human approval and an audit
   log ("an agent you can audit"). `docs/LEV_CORE8_BRAND_BRIEF.md` (PR #21,
   draft) proposes a different headline. One has to be chosen.
2. **Consent wording and privacy policy.** The form shows a placeholder.
3. **Form destination.** The platform already has a tested endpoint
   (`POST /api/public/lead-forms/{key}/submit`; see `docs/LAUNCH_READINESS.md`
   §9) but the platform has no production host. The field names here match it.
4. **Hosting and DNS** for the page itself, and who controls the domain today.
5. **Contact channels** to show (business email, WhatsApp), and the logo file.

## Tests

```
npm test               # 6 static checks: copy rules, i18n parity, no network code, contrast
npm run test:browser   # 6 browser checks, offline; needs Playwright and Chrome
```

Last recorded run (2026-11-19, Node 22.23.5, Playwright 1.63.0, Chrome 153,
Linux): 6 of 6 and 6 of 6 passed. Screenshots: `docs/evidence/landing-prototype/`.
Not tested: Firefox, Safari, real phones, screen readers.
