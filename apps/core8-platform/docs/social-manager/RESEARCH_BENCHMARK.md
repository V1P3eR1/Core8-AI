# Research & benchmark notes — 2026-10-27

Collected by Claude during the build session with web search/fetch (the container itself has no outbound internet for the RSS adapter, so these were gathered through the assistant's tools). All records are also seeded into the research inbox by `POST /api/social/starter-pack/seed` with `provider=claude-session`, `is_demo=0`, `trend_verified=0`.

## Sources (what they say → what it means for Core8AI)

| # | Source | Type | Takeaway | Unknown |
|---|---|---|---|---|
| 1 | TechCrunch, 2026-06-03 — [Meta's AI agent for WhatsApp Business is now available globally](https://www.techcrunch.com/2026/06/03/metas-ai-agent-for-whatsapp-business-is-now-available-globally/) | reporting, high | Meta Business Agent global in WhatsApp after ~2 years of tests; answers, recommends, books, qualifies, hands off to humans. Pricing: planned inclusion in some Premium tiers; token-based for large businesses (plans, not final). | Israel/Hebrew availability, final prices, customisation limits |
| 2 | AiChat vendor blog, 2026-06-15 — [Meta Conversations 2026 recap](https://www.aichat.com/blog/meta-conversations-2026-announcements) | opinion, medium | Business Agent + enterprise Platform (Shopify/Zendesk) + WhatsApp Business Discovery. Several claims are the vendor's opinion. | launch dates, paid tiers |
| 3 | Meta for Developers, 2026-07-29 — [Graph API v26](https://developers.facebook.com/blog/post/2026/07/29/introducing-graph-api-v26-and-marketing-api-v26/) | official, high | No IG publishing/insights changes; v20 removed 2026-09-24, v21 removed 2027-01-21 → bump our pinned version. | — |
| 4 | Meta for Developers — [Instagram Platform changelog](https://developers.facebook.com/documentation/instagram-platform/changelog) | official, high | 2026-06-22 `is_ai_generated` container flag + Story `link_clicks` (Facebook Login only); 2026-06-01 Audio API; 2026-07-30 `media_url` omitted for protected media. | effect of AI label on distribution |
| 5 | Meta for Developers — [Instagram Platform overview](https://developers.facebook.com/documentation/instagram-platform/overview) | official, high | Login paths, scopes, Standard vs Advanced Access, rate limits. Unified Login recommended for new integrations. | Unified Login specifics |
| 6 | FRBSF, 2026-09-01 — [AI adoption among small businesses (SBCS qualitative)](https://www.frbsf.org/research-and-insights/publications/system-research-san-francisco-fed/2026/09/ai-adoption-among-small-businesses-qualitative-insights-small-business-credit-survey/) | official, high | "Nearly 40%" of 2024 SBCS respondents use or plan to use AI; barriers: regulation, tool cost, time/staff, knowledge gaps; non-adoption: accuracy, IP, human interaction central. | US data, not Israel |
| 7 | FRBSF, 2026-03 — [Early findings on small business use of AI](https://frbsf.org/research-and-insights/publications/community-development-articles/2026/03/ai-and-small-businesses) | official, medium | Earlier companion article; not read in full. | findings |
| 8 | Anthropic — [The Briefing: Enterprise Agents](https://anthropic.com/events/the-briefing-enterprise-agents) | official, medium | Event page on enterprise agents; content not read. | date, content |

No source above supports a "trending" claim; all are labelled **relevant topic, trend not verified**.

## Benchmark summary (structure only — nothing is copied)

- **Gary Vaynerchuk** — [content strategy page](https://garyvaynerchuk.com/THE-GARYVEE-CONTENT-STRATEGY-HOW-TO-GROW-AND-DISTRIBUTE-YOUR-BRANDS-SOCIAL-MEDIA-CONTENT/): one long pillar piece → dozens of platform-specific micro pieces → daily distribution → micro drives back to the pillar. *Adopt:* one recorded conversation per week by Lev → reels/carousel/stories. *Don't:* the volume claims and the persona.
- **Alex Hormozi** — value-equation lens ([secondary summary](https://www.supersummary.com/100m-offers/summary/)): perceived value rises with the desired outcome and its likelihood, falls with the buyer's time and effort. *Adopt:* frame every post around the owner's time, effort and risk, not features. *Don't:* guarantees, scarcity tactics.
- **Dan Martell** — only secondary profiles were reachable ([Castmagic](https://www.castmagic.io/creators/dan-martell)); structure observed: principle → example → one step to apply, aimed at SaaS founders. *Low confidence; read primary material before relying on it.*
- **Meta / Zuckerberg** — product communication for business AI (via TechCrunch #1): capabilities described as everyday actions ("answers, recommends, books, hands off to a person"). *Adopt:* describe what the agent does on a Tuesday at 22:00, not its architecture.

## Deliverables produced from this research

- 20 distinct ideas → `agents.generate_ideas` mock bank (and live generation when a key exists); spread across the 9 pillars × 3 audiences × 4 formats.
- 3 complete Reel packages, 2 carousel packages, 5 Story concepts → `social/starter_pack.py` (status `draft`, origin `starter_pack`, every one requires Lev's review; the "Meta free agent" reel cites source #1).
- 30-day calendar → `GET /api/social/calendar` proposals from the editable content mix (hypothesis, not a guarantee).
