# Core8-AI — P1 carousel visual QA and approved-copy candidate

**Status:** DRAFT / NOT APPROVED / NOT PUBLISHED. Fictional Or Clinic scenario; no patient data, live integrations, real appointment booking or messages sent.

## Visual prototype review (23 November 2026)

Five generated 1080×1350 PNG slides exist as a **local review package**, not yet uploaded to this GitHub branch. Do not mark `calendar.csv` as `ASSET_READY` based on this note.

**Issues to fix before external use:**
1. Slide 3 depicts a **March 2025** calendar, which is an outdated illustrative date. Replace it with a clearly fictional undated schedule or relative-day labels.
2. Some tiny Hebrew text in generated UI mockups may be inaccurate. Rebuild important UI text as editable text rather than relying on image-generation lettering.
3. The first slide claims a "natural, fast" conversation; the existing receptionist demo is deterministic keyword rules, **not an LLM**. Replace with a factual claim about scripted routing.
4. The fifth slide shows an active automation switch; the actual demo offers an in-memory audit and simulated handoff, **not a live approval automation**. Remove or label the control fictional.
5. Check the logo against the actual Core8-AI brand asset and confirm rights to the typography, illustrations and icons.

## Corrected slide copy (HE, RTL)

| Slide | Headline | Body | English supporting line |
| --- | --- | --- | --- |
| 1 | מענה ראשוני לפניות | הדגמת שיחה עם פקידת קבלה וירטואלית למרפאה בדיונית. | Receptionist workflow demo |
| 2 | סיווג פניות | סיווג מבוסס מילות מפתח: תורים, שעות פעילות, מחירים או בקשה לנציג. | Rule-based intent routing |
| 3 | בקשת תור | הצגת שלושה מועדים לדוגמה בלבד. אין חיבור ליומן ואין יצירת תור אמיתי. | Hypothetical slots only |
| 4 | העברה לנציג | יצירת טיוטת פנייה לבדיקה אנושית. לא נשלחה הודעה. | Simulated human handoff |
| 5 | שקיפות ובקרה | תיעוד שלבי ההדגמה בדפדפן והורדת טיוטת ליד מקומית. | Local audit and draft export |

**Mandatory visible footer on every slide:** `הדמיה בלבד | DEMO / SIMULATION`

## Acceptance gates

- [ ] Replace inaccurate generated Hebrew with editable text.
- [ ] Correct slide 3's stale date and remove misleading production controls.
- [ ] Check text legibility at mobile width and RTL layout.
- [ ] Check product claims against `receptionist/engine.js` and `docs/DEMO_HANDOFF.md`.
- [ ] Confirm license/brand usage.
- [ ] Obtain owner approval before any social publishing.
- [ ] Export final PNG files and record asset checksum/version in the PR.

No customer-facing claims of autonomous AI, real bookings, or live Meta publishing until separately implemented and verified.
