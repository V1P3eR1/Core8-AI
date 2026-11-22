# Running the lead agent on the VPS (Hostinger KVM 2, Ubuntu 24.04 + Docker)

Status (2026-11-19): **running on the VPS, locked and not reachable.** The
container was started through Hostinger's Docker manager from
`docker-compose.hostinger.yml` on Lev's instruction. Its log shows the data
folder writable, sign-in locked (no password set) and the health check passing.
No port is published and the reverse proxy is not wired (platform PR #41), so
nothing can reach it from outside yet. The `Dockerfile` route below was never
built.

## What you get

- The agent at `https://agent.core8-ai.io`, behind a password.
- It reads the business inbox every five minutes, **read-only**, and only
  messages whose subject contains `[CORE8-LEAD]`.
- It drafts replies and proposes meeting times. It still cannot send anything.

## What only Lev can supply

1. **A login password** (12+ characters). Only its hash is stored.
2. **A Gmail app password** for the business mailbox (Google Account →
   Security → 2-Step Verification → App passwords). It can be revoked at any
   time without changing the real password.
3. **The form secret** already in the website's `server/lead-config.php`.

## Steps

The container starts **locked**: it serves the sign-in page and refuses every
login until the owner sets a password on the server. The password never
travels through a config file, a chat or the Hostinger API.

1. DNS: an `A` record `agent` → the VPS IPv4 address.
2. Start the container. Either through Hostinger's Docker manager with
   `deploy/docker-compose.hostinger.yml` (builds from the repository), or from a
   checkout: `docker network create core8-edge && docker compose -f deploy/docker-compose.yml up -d --build`
   (that variant reads `/etc/core8/lead-agent.env`; see `lead-agent.env.example`).
3. Set the password (hidden prompt, typed twice):
   ```
   docker exec -it core8-lead-agent node tools/set-password.cjs
   ```
   Run it again at any time to change the password; no restart is needed.
4. Reverse proxy: add `deploy/Caddyfile.snippet` to the Caddy that owns ports
   80/443 and attach that Caddy container to the `core8-edge` network. This
   touches the platform's deploy files, so it is a separate reviewed change.
5. Later, in the container's environment: `CORE8_LEAD_SECRET` (same value as in
   the website's `server/lead-config.php`) and the two `CORE8_PILOT_IMAP_*`
   values, then restart the container.
6. Check: `https://agent.core8-ai.io` shows the sign-in page; after signing in,
   the mailbox line reads "Mailbox checked … (read-only)".

## Hardening already in place

- No port is published on the host; only Caddy can reach the container.
- It starts locked until a password is set on the server, never open, and
  refuses to listen beyond loopback without a public host name.
- Container: non-root user, read-only filesystem, all capabilities dropped,
  memory and process limits.
- Session cookie: HttpOnly, Secure, SameSite=Strict, 12 hours. Five wrong
  passwords lock sign-in for 15 minutes.
- Requests with a foreign Host or Origin are refused; HSTS and a strict CSP are sent.
- The audit log is hash-chained; tampering shows in the UI.

## Known gaps before real use

- **Backups**: the `lead-agent-data` volume holds personal data (names, e-mails,
  messages). It needs a scheduled, encrypted backup and a retention rule that
  matches the privacy notice. Not built.
- **One user, one password**: no second factor, no per-user accounts.
- **Lockout is global**: someone who knows the address can keep sign-in locked.
  Restricting the site to known IPs in Caddy removes this.
- **Live model engine** is untested against the real API.
- **Not exercised on the real mailbox**: the reader is tested against a local
  fake IMAP server only.
- Sessions are in memory: a restart signs you out.
