# Publishing rules (canonical, enforced in code — `social/publishing.py`)

## Modes (`sm_settings.publishing.mode`)
1. `draft_only` — research + content only. Nothing is scheduled or published.
2. `approval_required` (DEFAULT) — only a specifically approved version can be
   scheduled and published. The approval binds account, caption, exact asset
   hashes, format, schedule and settings.
3. `automatic` — enabled only by an explicit owner action in settings, and only
   within boundaries: allowed categories (pillars), allowed account, posts per
   day, local time window, emergency pause, topics that always need review.

## Hard gates (all must pass; the LLM has no say)
- Emergency pause off.
- Not demo mode when the Instagram provider is live.
- Connected account id == approval account id == auto.allowed_account_id (automatic mode).
- Token present and not expired (live).
- Active approval whose binding hash matches the item right now.
- No sensitive flags unless a human approved after the flags were set.
- Asset spec check passed (format, size, dimensions per Meta docs).
- Reels: an actual video asset. Stories: account capability verified.
- Daily caps: Meta API limit (100/24h) and the owner's own `max_posts_per_day`.

## State machine (`sm_publications.state`)
queued → claimed → container_created → container_ready → publish_requested →
published | failed | needs_manual_review | cancelled

- One publication per approved version (`publication_key` unique).
- Claims are transactional (`UPDATE … WHERE state='queued'` with lock expiry);
  two workers cannot take the same row.
- After `publish_requested`, a timeout or ambiguous error does **not** retry
  blindly: the worker reconciles via the stored container id / provider media
  id. If it cannot verify, the publication becomes `needs_manual_review`.
- Retryable errors (network, 5xx, rate limit) retry up to `max_attempts` with
  backoff; permanent errors (invalid media, permission, expired token) fail.
- Exactly-once delivery is not promised; at-most-one *verified* publish per key is.

## Comments & DMs
Draft-only replies. Outbound replies stay disabled until explicitly enabled and
the Meta messaging permissions exist. Never send unsolicited DMs.
