# Core8-AI | First customer demonstration and lead handoff kit
Status: **READY FOR INTERNAL REVIEW — NOT A LIVE CUSTOMER CLAIM**
Owner: Lev · Source of truth: sprint #51 · prepared 2026-11-20

## Offer and positioning
**Hebrew:** פחות עבודה חוזרת. יותר זמן לעסק שלך.
**English:** Less repetitive work. More time for your business.

We identify a recurring operational workflow, demonstrate a bounded AI-assisted prototype and agree on integration, privacy and cost **before** any real customer implementation. The demonstration itself makes no claim of customer savings, completed bookings, 24/7 service or verified live integrations.

**Primary offer:** discovery conversation + bounded prototype + scoped implementation proposal. Pricing and delivery schedule follow a discovery process; no invented fixed fees or guarantees.

## Customer showcase | 5-minute walkthrough (HE)
1. **0:00–0:45 — Problem.** "כמה פניות העסק מקבל? באילו שעות? כמה פעמים עונים על אותן שאלות?" Ask the prospect to describe their own workflow. Do not state numbers.
2. **0:45–2:45 — Show existing offline receptionist.** The existing real code is in *draft* PR #26, `apps/customer-demos/receptionist/index.html` on branch `demo/p0-receptionist-or-clinic`. Explain that the example clinic and appointment slots are fictitious; the engine is keyword-rules-based for the demo. Run a simulated booking, show lead preview + human handoff, flip Hebrew/English, and demonstrate the urgent-message escalation. No live booking is created.
3. **2:45–3:45 — Lead follow-up concept.** Show the *draft design*, not a live integration: form from PR #32 → `CORE8 LEAD v1` HMAC email → triage from PR #31 → human-reviewed reply. Both PRs are unmerged; live email delivery and end-to-end production use are **not validated**. Explain the business inbox/privacy policy and consent as open go-live requirements.
4. **3:45–4:30 — Delivery control.** Show how draft vs approved vs published states work in the Social Manager on its current mock mode. Do not connect the customer's Meta account or claim real publishing. Use only owner-approved, non-confidential screenshots.
5. **4:30–5:00 — CTA.** "איזה תהליך אחד הכי שווה שנמפה ונבנה עבורכם הדגמה?" Agree on a discovery call. Record contact details only through approved, consent-based channels; until the website lead intake is approved, use a business-approved manual process.

## Customer discovery form — operator notes (never put customer data into public GitHub)
- Industry and point of contact, with consent to follow up.
- One repetitive process (incoming leads / scheduling / quotation requests / service status / content preparation).
- Current channels (web, phone, email, WhatsApp, social). No need to request account credentials.
- Human approval points, sensitive information involved, systems that would eventually need integration.
- Success metric to measure during a future pilot, baseline not yet known.
- Constraints: business hours, Hebrew/English, accessibility, security/compliance needs.
- Next step and owner. Record in an approved private lead system; not in this repo.

## Product boundaries and approval gates
| Component | Code state / evidence as of Nov 20 | Business-safe demonstration | Live go-live prerequisite |
|---|---|---|---|
| Receptionist | PR #26, draft, local/bilingual/offline; test evidence recorded in `docs/DEMO_HANDOFF.md` on its branch | **Yes, local mock** | Actual provider/integration, privacy/security and owner approval |
| Landing | PR #32, draft; PHP spool tests | **Preview only** | Consent/privacy/hosting/DNS, mail deliverability and production security |
| Lead triage | PR #31, draft; fake-IMAP tests | **Synthetic only** | Verified mailbox, backups/retention, signed intake, auth & owner approval |
| Social Manager | Main includes merged #9/#42/#43/#45; last documented VPS state: Instagram mock | **Yes, drafts/mock** | Meta app and Page/IG connection, account access, reviewed media & explicit first post approval |
| Multi-tenant SaaS | PR #38 is design proposal | **No production claims** | Tenant isolation security review and tests |

## Follow-up email copy (operator template, do not auto-send)
Subject: בהמשך להדגמת Core8-AI — בחינת תהליך לעסק

שלום [שם],
תודה על השיחה. כפי שהצגנו, ההדגמה היא סימולציה שממחישה קליטת פנייה, הכנת טיוטה והעברה לאישור אנושי — ללא הזמנות או הודעות אמיתיות.
השלב הבא שהצענו הוא שיחת אפיון קצרה לבחירת תהליך אחד, הבנת הכלים הקיימים והגדרת אב־טיפוס מוגבל שנוכל לבדוק יחד.
אם זה רלוונטי, אשמח לתאם זמן שמתאים לך.
בברכה,
Core8-AI

## Release steps
1. Independent review of PR #26 as customer-safe demo; don't publish it accidentally.
2. Add locally playable customer demo link to an approved Core8 landing **only after** testing and explicit approval.
3. Run synthetic producer→consumer tests and audit signed lead handling under #49.
4. Decide actual hosting/private data retention; obtain approved privacy wording and validate inbound email.
5. Review seven own-brand draft posts in `docs/launch/CORE8_SOCIAL_DRAFTS_HE_EN.md`.
6. Run Social Manager with mock publishing through approval + emergency pause; connect real Meta only with owner verification and approval.

**No accounts, actual contact records, credentials, invented customer results, ad spend, DNS, live email, merges or production publishing are authorized by this document.**

Links: #24 #26 #31 #32 #49 #51 #52 #11 #48.