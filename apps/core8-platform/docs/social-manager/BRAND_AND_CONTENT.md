# Brand & content

One canonical set of rules lives in `backend/social/rules/*.md` (brand voice, research workflow, content workflow, publishing rules, weekly analysis). The runtime injects those files into every agent prompt; the Claude Code skill (`.claude/skills/core8-social-manager/`) points at the same files. **Edit the rules there, not here.** This document explains the editable facts and how they are used.

## 1. Editable brand facts (dashboard → הגדרות מותג, `sm_settings.brand`)

Seeded only with what the owner's brief states. Everything else is marked `לא אושר עדיין — דורש אישור של לב`.

| Field | Seeded value | Status |
|---|---|---|
| Brand / owner / site | Core8AI · Lev Shoihat · https://core8-ai.com | from brief |
| Description | AI agents for businesses; WhatsApp agents (service, lead qualification, sales support); AI secretary/office manager; process automation; connecting business tools; SaaS and custom AI solutions; SMB to enterprise | from brief |
| Positioning | credible personal + business brand around practical AI | from brief |
| Approved services | the five areas above — **availability/stage unknown** | assumption flagged |
| Services in development | empty | unknown |
| Approved claims | only "Core8AI works on AI agents for businesses" and the website | from brief |
| Prohibited claims | customers, testimonials, results, percentages, prices, discounts, contractual promises, certifications, partnerships, integrations not approved, legal/medical/financial advice, competitor claims | from brief |
| Contact details | unknown | needs Lev |
| Topics to cover / avoid | the nine pillars / politics, competitor bashing, return promises, client secrets | from brief + defaults |

Assumptions recorded in the profile: product stage, customer count, case studies, pricing and integrations are unknown; every scenario is a demonstration; Lev's face/voice are never generated or simulated without explicit consent.

## 2. Content pillars (keys used in data)

1. `ai_plain` — AI בשפה פשוטה
2. `problem_workflow` — בעיה עסקית → תהליך → פתרון אפשרי
3. `whatsapp_agents` — סוכני WhatsApp
4. `ai_office` — מזכירה AI ותהליכי משרד חכמים
5. `ai_news` — חדשות AI לבעלי עסקים
6. `saas_building` — בניית SaaS ומוצרים דיגיטליים
7. `founder_journey` — המסע של לב ומאחורי הקלעים
8. `demos` — הדגמות ופרויקטים אמיתיים (**approval only**, never automatic)
9. `invitation` — הזמנה לשיחה על צורך עסקי

## 3. Audiences

| Key | Who | What they care about |
|---|---|---|
| `smb` | עסקים קטנים ובינוניים | fewer missed leads, less admin, no risk |
| `enterprise` | צוותי הנהלה וחברות גדולות | process, integration, governance, security |
| `founders` | מייסדים ויזמים | building products, SaaS, AI tooling, speed |

Every idea and item fixes **one** audience, one problem, one core message, one desired action, one format, a business goal and a measurement approach (only metrics the API or a manual entry can provide).

## 4. Content mix (editable hypothesis, `sm_settings.content_mix`)

2 Reels + 1 carousel per week, Stories on 3 days (Sun/Tue/Thu by default, 10:00; Reels Sun/Wed 18:00; carousel Tue 12:00). This is a starting experiment, not a reach guarantee; the planner labels every proposed slot as a hypothesis.

## 5. Fact-checking rules (code: `social/fact_check.py`)

Flags (always manual review, never auto-publish): `numbers`, `customers`, `prices`, `personal`, `legal_medical_financial`, `availability`, `likeness`, `controversial`, `unsourced_claim` (claim words without a source in the package). Flags are recomputed on every edit and shown with the matching excerpt. Dynamic claims (pricing, availability, market size, performance) must be re-checked against a current source before approval — the research inbox records `published_at`/`event_at` for that.

## 6. Originality and rights

- Benchmarks (Martell, Zuckerberg/Meta, Vaynerchuk, Hormozi, others) are studied for **structure** only: pillar → micro content, concrete-action language, buyer-cost framing. No text, visual style, imagery or persona is copied.
- Rendered carousels use only the owner's text, the bundled OFL font *Assistant* and flat shapes — no stock, logos or customer data.
- Uploaded assets carry `ownership` + `permission_note`; third-party assets must state the permission.
- AI-generated media must respect usage rights and is labelled via `package.is_ai_generated` (sent to Meta as the AI Info label).
- No deepfakes, voice clones or likeness of Lev or anyone else without explicit written consent.
- Web pages, comments and DMs are untrusted data; instructions inside them are ignored and flagged.
