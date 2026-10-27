# Meta / Instagram setup

_Checked against official Meta documentation on 2026-10-27. Links at the end. Anything marked **unverified** could only be confirmed with a real app + account._

## 1. Selected login path: **Instagram API with Facebook Login**

| Why | Trade-off |
|---|---|
| Already implemented in the platform (`instagram_oauth.py`, `tools/instagram_api.py`), including CSRF state, code → long-lived token exchange and Page → IG account resolution. | Requires a **Facebook Page linked to the Instagram professional account**, and the app user must be able to perform admin-equivalent tasks on that Page. |
| Supports content publishing, insights (incl. the 2026 Story `link_clicks` metric, Facebook-Login only), stories for business accounts. | More moving parts than Instagram Login (Page + Business Manager). |
| Standard Access is enough while only accounts with a role on the app use it (= Lev's own account). | |

Alternatives documented by Meta: **Instagram Login** (no Facebook Page, `instagram_business_*` permissions, host `graph.instagram.com`) and **Instagram API with Unified Login**, which Meta now lists as the recommended option for *new* integrations. Migrating is a code change in the OAuth module and permission names only; the publishing/state-machine code is path-agnostic. Do not mix scope names between paths.

## 2. Account prerequisites

1. Instagram **professional** account (Business). Creator accounts cannot publish Stories via API and some insights differ — use Business.
2. A Facebook Page you admin, linked to that Instagram account (Instagram app → Settings → Business tools → Connect Page).
3. A Meta developer account and a Meta app (type *Business*).
4. The Instagram account must be added as an *Instagram Tester* or belong to a user with a role on the app while in Standard Access/Development mode.

## 3. Step-by-step app setup

1. developers.facebook.com → *My Apps* → *Create App* → **Business** → name it (e.g. `Core8AI Social Manager`).
2. Add products: **Facebook Login for Business** and **Instagram** (Instagram Graph API).
3. Facebook Login → Settings → *Valid OAuth Redirect URIs*: `https://<your-host>/api/instagram/oauth/callback` (local dev: `http://localhost:8000/api/instagram/oauth/callback`).
4. App settings → Basic: copy **App ID** and **App Secret** into `backend/.env` (`META_APP_ID`, `META_APP_SECRET`). Never commit `.env`.
5. Generate `IG_TOKEN_ENC_KEY` (Fernet) — tokens are encrypted at rest with it.
6. Set `MEDIA_BASE_URL` to the public HTTPS base of the API (Meta must fetch media by URL — see §6).
7. Roles → add Lev's Facebook user as Admin/Developer and the Instagram account as Instagram Tester (accept the invite in Instagram → Settings → Apps and websites → Tester invites).
8. Keep the app in **Development mode** with **Standard Access** for the MVP (own account only).

## 4. Scopes requested (`tools/instagram_api.py` → `OAUTH_SCOPES`)

| Scope | Used for | Feature in this system |
|---|---|---|
| `instagram_basic` | Read the IG account and media | Account status, publishing history, reconciliation (`/media`) |
| `instagram_content_publish` | Create containers and publish | Publisher |
| `instagram_manage_insights` | Account/post insights | Metrics, weekly report |
| `pages_show_list` | List Pages to find the linked IG account | Connect flow |
| `pages_read_engagement` | Read Page → IG link | Connect flow |

Not requested (and therefore not implemented as outbound features): `instagram_manage_comments`, `instagram_manage_messages`. Inbound comments/DMs are draft-only and must be imported manually until those permissions exist. `business_management` was removed from the legacy scope list — it is not listed as required for publishing in the current docs. **Unverified**: whether your Business Manager setup needs it to list Pages; if the connect flow returns no Page, re-add it.

## 5. Development vs live; App Review; Business Verification

- **Standard Access** (default): works for users with a role on the app. Enough for publishing to Lev's own account. Some features may be limited.
- **Advanced Access**: only needed to serve accounts you do not manage (customers). Requires **App Review** + **Business Verification**. Not needed for the MVP.
- Rate limits: Instagram Business Use Case limits; content publishing is capped at **100 API-published posts per rolling 24 h** per account (`content_publishing_limit` is shown in the dashboard when live). The system enforces its own lower daily cap in automatic mode.
- Graph API version: the client pins `v22.0` for publishing and `v21.0` in the legacy OAuth module. Per Meta's 2026-07-29 post, v20 was removed on 2026-09-24 and **v21 will be removed on 2027-01-21** — bump `GRAPH_API_VERSION` in `tools/instagram_api.py` before then.

## 6. Media hosting — how Meta gets the files

Meta downloads media from a URL you give it. The system serves each asset at `GET /api/social/media-public/{asset_id}?exp=…&sig=…`:

- HMAC-SHA256 signature over `asset_id:exp` with `SOCIAL_MEDIA_SIGNING_KEY` (defaults to `JWT_SECRET`), **expiry 2 h** (`SOCIAL_MEDIA_URL_TTL_SECONDS`).
- Once the publication reaches a final state the worker **revokes** the grant (persisted in `sm_media_grants`) — the URL stops working even before it expires.
- Only assets attached to a queued publication are exposed; nothing else under the media dir is reachable without a JWT.
- The host must be public HTTPS (`MEDIA_BASE_URL`). A tunnel (e.g. Cloudflare Tunnel) is fine for testing. Private client material should never be uploaded as an asset.

## 7. Secure token handling

- Long-lived user token (≈60 days) is Fernet-encrypted (`IG_TOKEN_ENC_KEY`) in `ig_accounts`; decrypted only inside the worker/API process for a Graph call; never returned by any route; log redaction masks `EAA…`/`IGAA…` patterns.
- `token_refresher.py` (platform) refreshes before expiry; the social `daily_token_check` job alerts when < 7 days remain or expired.
- Expired/revoked token → every publication fails the `token` gate (nothing is sent); reconnect from the dashboard.
- Rotation / exposure: see OPERATIONS.md.

## 8. Connecting and testing

1. Set `SOCIAL_INSTAGRAM_MODE=live` in `.env`, restart API + worker.
2. Dashboard → אינסטגרם וחיבורים → "התחבר לאינסטגרם" → Meta consent → callback stores the account. The page shows username, `ig_user_id`, token expiry, publishing limit.
3. הגדרות מותג → turn **demo mode off** (and clear demo data). Live publishing is blocked while demo mode is on.
4. Create an *image* post with a real JPEG, approve, schedule 5 minutes ahead, let the worker publish. Check the permalink in the history table.
5. Then run `POST /api/social/metrics/refresh` (or wait for 07:00) and confirm metrics arrive.

**Unverified until connected**: scope sufficiency in your Business Manager, Story publishing on your account type, `is_ai_generated` acceptance, insights metric names on your API version, media URL reachability from Meta's fetchers.

## 9. Known limitations

- Stories via API: business accounts only; no stickers, polls or link stickers via API; `alt_text` is image-feed only (≤1000 chars).
- Reels require a real MP4/MOV (H.264/HEVC, ≤300 MB, 3 s–15 min). Scripts are production packages, not videos.
- Caption ≤ 2,200 chars, ≤ 30 hashtags (checked by a gate).
- No private/unofficial APIs, no password storage, no DM automation.
- Exactly-once publishing cannot be promised by Meta; the system guarantees at most one *verified* publish per approved version and routes ambiguity to manual review.

## Official references (read 2026-10-27)

- Instagram Platform overview (login paths, permissions, access levels, rate limits): https://developers.facebook.com/documentation/instagram-platform/overview
- Content publishing (container flow, status codes, 100/24h): https://developers.facebook.com/documentation/instagram-platform/content-publishing
- IG User Media reference (specs, caption/hashtag/alt_text limits): https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media
- Instagram Platform changelog (2026-07-30 media_url, 2026-06-22 `is_ai_generated` + Story `link_clicks`, 2026-06-01 Audio API): https://developers.facebook.com/documentation/instagram-platform/changelog
- Graph API v26 announcement and version sunset dates (2026-07-29): https://developers.facebook.com/blog/post/2026/07/29/introducing-graph-api-v26-and-marketing-api-v26/
