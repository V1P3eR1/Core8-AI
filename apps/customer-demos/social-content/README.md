# Core8-AI — offline social portfolio storyboard (P1 draft)

**DRAFT / SIMULATION ONLY.** All examples are fictional and illustrative. No content has been published, scheduled, approved, sent to customers, or connected to a social account. This is a storyboard, not rendered assets or a finished portfolio UI.

## Five-panel portfolio carousel — proposed storyboard

| Panel | Visual direction | Headline (HE / EN) | Evidence/status |
|---|---|---|---|
| 1 | Phone mockup with fictional clinic conversation | מענה ראשוני חכם / Smarter first response | PROPOSED — visual not produced |
| 2 | Intent labels and routing arrows | סיווג פניות / Inquiry triage | PROPOSED — deterministic offline demo exists in PR #26, not AI inference |
| 3 | Calendar with clearly marked hypothetical slots | בקשת תור / Appointment request | PROPOSED — no real calendar connection |
| 4 | Lead card with DRAFT watermark | מסירה לנציג / Human handoff | PROPOSED — no notification sent |
| 5 | Audit trail and explicit simulation banner | שקיפות ושליטה / Human control | PROPOSED — no production KPI claim |

## Educational reel — storyboard only

| Time | Shot | On-screen copy |
|---|---|---|
| 0–4 s | Fictional incoming inquiry | “What happens when a customer writes after hours?” |
| 4–9 s | Local rule-based intent classification | “Classify the request (simulated)” |
| 9–14 s | Three hypothetical appointment slots | “Prepare a request — not a confirmed booking” |
| 14–19 s | Human review card | “A person stays in control” |
| 19–24 s | Core8-AI name and demo disclaimer | “Explore the offline demonstration. No messages sent.” |

Do not use real customer names, contact details, social account identifiers, Meta API tokens, live analytics or unapproved testimonials. Keep personal LEV branding separate from Core8-AI. Do not promise ROI, response time, conversion rates or continuous availability without evidence.

## Calendar contract

[calendar.csv](calendar.csv) has exactly two rows and the required DRAFT, NOT_APPROVED and NOT_PUBLISHED markers. Platform and account are placeholders. Scheduling is TBD. This file is not a publishing queue.

## Acceptance and next steps

- [x] Five-panel **text storyboard** and separate educational reel storyboard.
- [x] Exactly two HE/EN calendar draft rows with explicit unpublished states.
- [ ] Design/render actual five-panel carousel and reel assets.
- [ ] Human review of copy, claims, accessibility, brand and licensing.
- [ ] CI validation of CSV schema, row count, and no real account references.
- [ ] No publishing until separate account authorization and approval.
