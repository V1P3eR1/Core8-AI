# Core8AI Social Manager

AI-assisted Instagram management for Core8AI: research → ideas → Hebrew content packages → approval → scheduled publishing via the official Meta API → measurement → weekly report. Built **inside** the Core8 platform (`apps/core8-platform`) as an additive module: `backend/social/` + `frontend/app/social/`.

| Doc | What |
|---|---|
| [STATUS.md](STATUS.md) | What is verified, what waits for credentials, what is not built, risks |
| [META_SETUP.md](META_SETUP.md) | Meta app, login path, scopes, review, connecting the account |
| [OPERATIONS.md](OPERATIONS.md) | Worker/scheduler deployment, backups, token rotation, emergency pause, recovery |
| [BRAND_AND_CONTENT.md](BRAND_AND_CONTENT.md) | Brand facts, pillars, audiences, fact-checking, originality rules |
| [RESEARCH_BENCHMARK.md](RESEARCH_BENCHMARK.md) | Sources collected on 2026-10-27 + benchmark notes |
| [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md) | Decisions and phase log |

## What the system does

- **Research inbox** — RSS feeds of official publishers (no key needed) or manual entry; duplicate detection by normalised URL; every record keeps URL, publisher, dates, source type, confidence, relevance, unknowns and an original angle. Trends are never "verified" by the model.
- **Ideas & drafts** — Strategist/Writer/Producer modules (Claude when `ANTHROPIC_API_KEY` is set, deterministic mock otherwise) produce Reel, carousel, image and story packages. A deterministic **fact checker** flags numbers, customer/result claims, prices, personal data, advice, availability, likeness and controversial text; flagged items can never be auto-published.
- **Carousel rendering** — real 1080×1350 JPEGs, Hebrew RTL (Pillow + libraqm), bundled OFL font *Assistant*, editable templates, preview before export.
- **Approval binding** — an approval hashes account + caption + exact asset SHA-256s + format + schedule + settings. Any change invalidates it (code, not prompt).
- **Publisher state machine** — `queued → claimed → container_created → container_ready → publish_requested → published | failed | needs_manual_review | cancelled`, transactional claims, unique publication key, retry with backoff for transient errors, **reconciliation instead of blind retry** after an ambiguous timeout, emergency pause.
- **Three modes** — `draft_only`, `approval_required` (default), `automatic` (explicit owner action + category/account/frequency/time-window boundaries).
- **Jobs & schedules** — daily research 08:30, planning Sunday 09:00, weekly report Thursday 18:00, metrics 07:00, token check 07:15 (Asia/Jerusalem, DST-aware, editable). Missed jobs are marked `skipped`. Worker heartbeat → dashboard warning when offline.
- **Metrics & weekly report** — only API values or manual entries; missing metrics are named; observations and recommendations are separate lists; no ROI/attribution.
- **Leads** — manual tracker with retention purge. No outbound DMs. Inbound comments/DMs: draft-only replies.
- **Demo vs live** — demo records carry `is_demo=1` and a DEMO badge, are seeded on first boot while `demo_mode` is on and removable with one click. Live publishing is impossible while `demo_mode` is on.

## What works now vs. what needs you

| Area | State |
|---|---|
| Everything above in **mock** Instagram mode, **mock** LLM mode | Working and tested (81 backend tests) |
| Live research via RSS | Code complete; needs outbound internet from your machine (blocked in the build sandbox) |
| Claude-written content | Needs `ANTHROPIC_API_KEY` |
| Real Instagram publishing / insights | Needs Meta app + connected account (see META_SETUP.md); **unverified** until then |
| Reels | Need an actual video file — the system never pretends a script is a video |

## Prerequisites

Python 3.12+, Node 20+, `ffprobe` (optional, for video duration/codec checks), libraqm (ships with Pillow wheels on Windows/macOS/Linux).

## Local installation

```bash
cd apps/core8-platform/backend
python -m venv .venv && .venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env                                   # set JWT_SECRET (long random), DEV_MODE=true; keys optional
cd ../frontend && npm install
```

## Database

SQLite file `backend/core8.db` (or `DB_PATH`). Migrations run automatically on boot (`social/schema.py`, versioned in `sm_migrations`). No manual step.

## Running

```bash
# 1) API (terminal 1)
cd apps/core8-platform/backend && uvicorn main:app --reload        # http://127.0.0.1:8000

# 2) Worker (terminal 2) — scheduler + publisher
cd apps/core8-platform/backend && python -m social.worker

# 3) Dashboard (terminal 3)
cd apps/core8-platform/frontend && npm run dev                      # http://localhost:3000/social
```

Dev shortcut: `SOCIAL_WORKER_INPROCESS=true` runs the worker inside the API process (not for production).

## Demo walkthrough (no credentials)

1. Open `http://localhost:3000/social`, create the first admin (one-time setup).
2. **סקירה כללית** — modes show `Instagram: mock`, `LLM: mock`. Demo records are seeded (DEMO badge). Optional: **starter pack** (`POST /api/social/starter-pack/seed` or the button in settings) adds the real sources and original drafts from the build session.
3. **מחקר ומגמות** → "הרץ מחקר עכשיו". In mock mode you get labelled demo sources; on your machine with internet, live RSS.
4. **רעיונות לתוכן** → "צור 20 רעיונות" → pick a carousel idea → "צור טיוטה".
5. **יצירת תוכן** → edit slides → preview → "רנדר קרוסלה" (JPEGs appear under נכסים וקבצים) → set a schedule → "שלח לסקירה".
6. **אישורים** → check gates → "אשר" → "תזמן".
7. **אוטומציות ולוגים** → if the worker is running it publishes at the scheduled time (mock: instantly, with a fake permalink). Or press "הרץ tick".
8. **ביצועים ודוחות** → "צור דוח שבועי" — note the missing-metrics list.
9. **סקירה כללית** → "נקה נתוני demo" to remove every demo record.

Same flow from the API: see `backend/tests/test_social.py::test_demo_flow_research_to_report`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Red banner "ה-worker לא פעיל" | `python -m social.worker` is not running (or heartbeat stale > 3×poll). Start it. |
| Research run stores 0, errors `ProxyError`/`ConnectError` | No outbound internet. Check the feeds list / proxy. Mock mode is used automatically only when `SOCIAL_RESEARCH_MODE=mock`. |
| "demo_vs_live" gate fails | `demo_mode` is on while `SOCIAL_INSTAGRAM_MODE=live`. Clear demo data and turn demo mode off in הגדרות מותג. |
| "token" gate fails | Token missing/expired → reconnect in אינסטגרם וחיבורים. |
| Carousel text looks unshaped | libraqm missing: `python -c "from PIL import features; print(features.check('raqm'))"` should print True. |
| Publication stuck in `needs_manual_review` | Outcome unknown. Check Instagram manually, then **resolve** with the real media id or mark failed. Never re-queue blindly. |
| `IG_TOKEN_ENC_KEY` error | Generate a Fernet key (see `.env.example`). Changing it invalidates stored tokens → reconnect. |
