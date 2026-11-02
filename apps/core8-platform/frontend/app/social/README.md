# Core8AI Social Manager — frontend (`/social`)

Hebrew, RTL dashboard for the Social Manager API (`backend/social/routes.py` is the contract).
Everything lives under `app/social/`, `components/social/` and `lib/social-api.ts`; nothing in `backend/` is touched.

## Pages

| Route | Hebrew label | Main API calls |
|---|---|---|
| `/social` | סקירה כללית | `GET /overview`, `POST /settings/emergency-pause`, `POST /demo/seed`, `POST /demo/clear` |
| `/social/research` | מחקר ומגמות | `GET/POST /sources`, `PATCH /sources/{id}`, `POST /research/run` |
| `/social/ideas` | רעיונות לתוכן | `GET/POST /ideas`, `PATCH /ideas/{id}`, `POST /ideas/generate`, `POST /ideas/{id}/draft` |
| `/social/content` | יצירת תוכן | `GET/POST /items` (grouped by status, filters) |
| `/social/content/[id]` | עריכת פריט | `GET/PATCH/DELETE /items/{id}`, `/status`, `/approve`, `/schedule`, `/gates`, `/render-carousel`, `GET /carousel/templates`, `POST /carousel/preview`, `GET /assets` |
| `/social/calendar` | לוח פרסומים | `GET /calendar`, `PUT /settings/content_mix` |
| `/social/approvals` | אישורים | `GET /items` + `/gates`, `/approve`, `/schedule`, `/status` |
| `/social/assets` | נכסים וקבצים | `GET/POST /assets`, `PATCH/DELETE /assets/{id}`, `GET /assets/{id}/file` (blob) |
| `/social/instagram` | אינסטגרם וחיבורים | `GET /instagram/status`, `/history`, `POST /instagram/connect-url`, `GET /publications` + cancel/reconcile/resolve, `GET/POST /inbound`, `/draft-reply`, `PATCH /inbound/{id}` |
| `/social/leads` | פניות ולידים | `GET/POST /leads`, `PATCH/DELETE /leads/{id}`, `POST /leads/purge` |
| `/social/performance` | ביצועים ודוחות | `GET /metrics`, `POST /metrics/manual`, `/metrics/refresh`, `GET /reports`, `POST /reports/weekly` |
| `/social/brand` | הגדרות מותג | `GET/PUT /settings/brand`, `/settings/publishing`, `GET/PUT /carousel/templates` |
| `/social/jobs` | אוטומציות ולוגים | `GET /jobs`, `POST /jobs`, `/jobs/{id}/retry`, `PATCH /schedules/{key}`, `POST /worker/tick`, `GET /audit` |

## Structure

- `app/social/layout.tsx` — wraps everything in `<div dir="rtl" lang="he">` with the Heebo font and `SocialShell`.
- `components/social/SocialShell.tsx` — auth gate (refresh token → `/api/auth/me`, else `LoginPage`; first-run setup detected via `POST /api/auth/setup` ≠ 403), sidebar (drawer on mobile), header with provider modes, worker/emergency banners, `useSocialStatus()` context (overview polled every 60s, `refresh()` after mutations).
- `components/social/ui.tsx` — Button, Card, Badge, DemoBadge, StatusBadge, ModeBadge, Field/Input/Select/Textarea/Checkbox, Modal (focus trap, Esc), ConfirmButton, Tabs, Table, EmptyState, Loading, ErrorBox, Banner.
- `components/social/toast.tsx` — `ToastProvider` / `useToast()`; `toast.error(err)` renders `ApiError` messages (`detail` string, `{code,message}` or pydantic lists).
- `components/social/hooks.ts` — `useLoad` (load + reload), `useAssetUrl` (authenticated blob → object URL), `useBusy`.
- `components/social/PackageEditor.tsx` — per-format package editors (reel / carousel with slides + live preview / image / story) + raw-JSON fallback.
- `components/social/AssetThumb.tsx` — authenticated thumbnail.
- `lib/social-api.ts` — `api.*` typed client over `apiFetch` (JWT + auto refresh), types, Hebrew label maps, date helpers.

## How data labels work

- **DEMO badge (yellow)** — shown on any record with `is_demo === 1`, metric `source === "demo"`, or publication `mode === "mock"`. `isDemo()` in `lib/social-api.ts` is the single rule. Demo records are visible only while `publishing.demo_mode` is on (header shows "מצב DEMO").
- **Provider modes** — header badges for Instagram / LLM / מחקר come from `GET /overview.modes`; green = `live`, yellow = `mock`. Pages show a banner when their provider is not live (research: "ספק מחקר לא מחובר", metrics refresh shows the API's `reason`).
- **Worker** — red banner "ה-worker לא פעיל — ג'ובים ופרסומים לא ירוצו" when `worker.online === false`; red banner when `publishing.emergency_pause` is true.
- **Dates** — always the `*_local` ISO fields (Asia/Jerusalem) formatted with `Intl.DateTimeFormat("he-IL", {timeZone:"Asia/Jerusalem"})` (`fmtLocal`); raw UTC `created_at`-style strings go through `fmtUtc`. Schedule inputs are `datetime-local` and are sent as `YYYY-MM-DDTHH:mm` (the API interprets them as Asia/Jerusalem).
- **Missing values** — rendered as "חסר"; metrics are never estimated (missing account metrics are listed as dashed cards).
- **Approval binding** — the item page warns that editing caption / assets / schedule / account after approval invalidates the approval (`approval.reason` is translated, e.g. "changed:caption_hash" → "השתנו: כיתוב").
- **Trend** — sources show "טרנד מאומת" only when `trend_verified === 1`, otherwise "נושא רלוונטי — טרנד לא מאומת".
- **Calendar** — solid chips are real items (colour by status); dashed chips are planner proposals ("הצעה — היפותזה"), never items.
