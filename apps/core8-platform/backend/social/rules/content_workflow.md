# Content workflow (canonical)

Pipeline: source → idea → draft (package) → fact check → review → approval →
scheduled → publishing → published / failed / needs manual review.

## Idea (sm_ideas)
Each idea fixes: one primary audience, one problem, one core message, one
desired action, one format, a business goal and how it will be measured.

## Reel package (format = reel)
hooks (3 alternatives) · audience + problem · script with approximate duration
· shot list · on-screen text / subtitles · cover text · caption · one CTA ·
sources for every claim · required assets · production status
(`script_only` → `assets_missing` → `ready_to_render` → `ready_to_publish`).
A script is **not** a video. A reel cannot be scheduled without an actual video asset.

## Carousel package (format = carousel)
hook + structure · slide-by-slide Hebrew copy (2–10 slides for the MVP renderer) ·
visual direction · caption · CTA · sources and verification notes.
Rendering: `social/carousel_render.py` produces 1080×1350 JPEGs (RTL, Assistant font).

## Single image / Story
Story = content package; API publication only when the connected account is a
business account and the capability check passes (stories are business-only
per Meta docs). Stories cannot carry alt text or link stickers via API.

## Fact checker
Flags any sentence with: numbers/percentages, customer or result claims,
prices/discounts/contracts, personal data, legal/medical/financial advice,
product availability, a person's likeness, negative/controversial claims.
Flagged items can never be auto-published; they require manual review.

## Editing
Any change to caption, assets, account, format, schedule or publication
settings after approval invalidates the approval (code-enforced, see
`social/approvals.py`).
