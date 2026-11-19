# Running the lead agent on the VPS (Hostinger KVM 2, Ubuntu 24.04 + Docker)

Status: **prepared, not deployed.** Nothing in this folder has been run on a
server. Deploying needs Lev's explicit approval and the secrets listed below,
which only he can create.

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

1. DNS: add an `A` record `agent` → the VPS IPv4 address.
2. On the server, get the code and create the env file:
   ```
   sudo mkdir -p /etc/core8 && sudo cp deploy/lead-agent.env.example /etc/core8/lead-agent.env
   sudo chmod 600 /etc/core8/lead-agent.env      # then fill it in
   ```
3. Make the password hash (prompts without echo) and paste it into the env file:
   ```
   docker compose -f deploy/docker-compose.yml build
   docker compose -f deploy/docker-compose.yml run --rm --no-deps lead-agent node tools/hash-password.cjs
   ```
4. Start it:
   ```
   docker network create core8-edge
   docker compose -f deploy/docker-compose.yml up -d
   ```
5. Reverse proxy: add `deploy/Caddyfile.snippet` to the Caddy that owns ports
   80/443, attach that Caddy container to the `core8-edge` network, reload Caddy.
   This touches the platform's deploy files, so it is a separate reviewed change.
6. Check: `https://agent.core8-ai.io` shows the sign-in page; after signing in,
   the mailbox line reads "Mailbox checked … (read-only)".

## Hardening already in place

- No port is published on the host; only Caddy can reach the container.
- The process refuses to start on a public address without a password, and
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
