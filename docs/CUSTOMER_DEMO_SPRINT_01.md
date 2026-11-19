# Core8-AI | Claude Code Sprint 01 — Customer Demos

**GitHub intake:** https://github.com/V1P3eR1/Core8-AI/issues/24

**Scope:** Build customer-presentable offline demos in a new isolated `apps/customer-demos/` folder. This branch is **not** production. No live API integrations, publishing, deployments, main merges, or secrets.

## Read these first
- `docs/CORE8_INVENTORY.md`
- `docs/AGENTS_CATALOG.md`: verified seeded IDs in code are `general`, `leads`, `calendar`, `design`, `instagram`. Only the IG agent had scoped tools at last audit; reverify.
- `docs/ARCHITECTURE.md`
- Issues #7, #10, #11 (security gate).
- Keep `apps/my-goddess-orchestra/` separate.

## Deliver in this order
1. **P0 — Receptionist customer demo**: static HE/EN offline UI for fictional 'Or Clinic'. Interactive mock intake → intent → three *hypothetical* slots → confirmation draft → human review. Sample identity must be explicitly fictional. Persistent local-demo banner, no booking claim, no network calls; responsive UI.
2. **P1 — Marketing assets**: portfolio carousel of 5 panels, standalone AI education reel storyboard, two-row `calendar.csv` (status DRAFT / account placeholder).
3. **P1 — Internal Agent Studio**: stand-alone from control center, sales, verification and execution. Linked agents, proposed skills, 01–42 *unverified* capability placeholders, tasks, output paths, tests, dependencies, blockers, statuses, evidence, source and ownership. Search filters and HE/EN.
4. **P2 — Industry variants**: real estate and car service with fake data.

## Acceptance
- Open offline without API credentials and without internet.
- Complete interactive demo happy path and human escalation.
- HE RTL ↔ EN LTR.
- Exactly 5 portfolio panels and exactly 2 calendar CSV data rows.
- Local browser smoke test and screenshot evidence.
- No browser-shipped secrets; no customer data.
- Attach command output and explicit limitations in `docs/DEMO_HANDOFF.md`.

## Non-negotiable boundaries
- No direct commits to main, no merge, no production or DNS change.
- No assumptions about connected Gmail, Calendar, Metricool, WhatsApp, Meta or customers.
- Existing runtime security risks (#11), tenant isolation (#7) block public production onboarding.
- Open a **draft PR** and request human review.
- Never label tests VERIFIED until evidence from an actual run is attached.

## Demo pitch
'Core8-AI demonstrates how an AI receptionist can handle inquiries and prepare a booking request, with escalation to a human. The mockup uses fictitious availability; production integrations and results require separate configuration and validation.'

**Ownership:** Claude Code: code / tests / PR; ChatGPT: messaging / acceptance review; Lev: approve merge and any external action.
