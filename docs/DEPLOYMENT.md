# Deployment

_Audit date: 2026-10-01 · Current state + how to run. No production deployment of the
platform was found._

## 1. Current state

| App | Where it runs today |
|---|---|
| Core8 Platform | Lev's Windows machine (`start-backend.ps1`, `start-frontend.ps1`). Production compose exists but no evidence it is deployed. |
| My Goddess | Lev's Windows machine, `http://localhost:8420`. |
| Static sites | Netlify `qa-core8-ai.netlify.app`, `clinquant-peony-4aa4fb.netlify.app` (manual drops, 2026-07-09). |
| Supabase | Project exists (ap-southeast-1), hibernated, unused by code. |
| Vercel / Lovable | Nothing deployed. |

## 2. Core8 Platform — local development

Prereqs: Python 3.12, Node 20+.

```bash
# backend
cd apps/core8-platform/backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # fill ANTHROPIC_API_KEY, JWT_SECRET; never commit .env
uvicorn main:app --reload   # http://127.0.0.1:8000/api/health

# frontend (see TECH_DEBT C1/C2 first: shadcn ui components + lockfile)
cd apps/core8-platform/frontend
cp .env.local.example .env.local
npm install
npx shadcn add button dialog label textarea scroll-area
npm run dev                 # http://localhost:3000
```

First run: `POST /api/auth/setup` creates the first admin user (via the login page).

## 3. Core8 Platform — production (docker-compose)

`apps/core8-platform/docker-compose.yml` defines:

| Service | Image | Exposure |
|---|---|---|
| `backend` | `./backend/Dockerfile` | internal :8000, `DEV_MODE=false`, DB on volume `db_data:/data` |
| `frontend` | `./frontend/Dockerfile` | internal :3000, built with `NEXT_PUBLIC_API_URL=https://$DOMAIN` |
| `nginx` | `nginx:1.27-alpine` | public :80/:443, TLS from `./nginx/ssl`, certbot webroot volume |

Steps on a VPS:
1. Create `backend/.env.production` on the server (from `.env.example`) — **never in git**.
2. Place TLS certs in `nginx/ssl/` (or run certbot against `certbot_www`).
3. `DOMAIN=core8-ai.com docker compose up -d --build`.
4. Back up the `db_data` volume (contains users, leads, encrypted IG tokens).
5. Instagram: set `META_REDIRECT_URI=https://$DOMAIN/api/instagram/oauth/callback` and a public `MEDIA_BASE_URL` so Meta can fetch post media.

## 4. My Goddess — local

```bash
cd apps/my-goddess-orchestra/master-control
pip install -r requirements.txt
# persona library is NOT in this repo — clone agency-agents next to master-control
# or set AGENCY_DIR=/path/to/agency-agents
export ANTHROPIC_API_KEY=...   # Windows: setx ANTHROPIC_API_KEY "..." then new terminal
python server.py               # http://localhost:8420 (Chrome/Edge for voice)
```

Localhost only — it has no authentication.

## 5. Secrets policy

- Secrets live only in local `.env` files, host environment variables, or a secret manager.
- Only `*.example` templates are committed. Root `.gitignore` blocks `.env*`, keys, `*.db`, data folders.
- `.github/workflows/secret-scan.yml` runs gitleaks over full history and blocks env/key/db files on every PR and push to `main`.
- If a secret is ever committed: rotate first, then purge history.

## 6. Open deployment decisions

- Hosting target for the platform (VPS + compose vs. managed: Fly/Render/Railway; Vercel for frontend).
- SQLite → Supabase Postgres migration timing.
- Whether `core8-ai.com` should point at the Netlify landing site or the platform.

## Upgrading an existing database to multi-tenancy (CORE8-005)

On the first start of a build that includes CORE8-005, the backend detects a pre-tenancy
database and writes a consistent copy next to it **before changing anything**:
`<DB_PATH>.pre-core8-005-<UTC timestamp>.bak` (mode 600; contains customer data; git-ignored).

- **Verify:** log in, check leads/conversations/Instagram for the Core8 internal tenant.
- **Rollback:** stop the stack, copy the `.bak` file over `DB_PATH`, deploy the previous build.
  The upgrade can be re-run later from the restored file.
- **After verification:** delete the `.bak` file (or move it to encrypted, access-controlled
  backup storage). Never copy it to Drive or other synced folders.
- Rehearse this once on a sanitized copy of the production database before the real upgrade.

## First admin account

Set `SETUP_KEY` (long random string) in the backend environment before the first start, then call
`POST /api/auth/setup` with `email`, `password` and that `setup_key`. Without the key, setup is
refused when `DEV_MODE=false`. The endpoint disables itself once a user exists; remove `SETUP_KEY`
afterwards.
