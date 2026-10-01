# My Goddess — QA Audit & Hardening Report
**Date:** 2026-07-29 · Reviewer: Fable 5 (acting QA engineer)
**Scope:** `server.py`, `static/index.html` — treated as a production service for a large company.

## Method
Read both files end to end; ran the server under a test client with adversarial inputs
(malformed payloads, oversized input, injection strings, tool failures, missing key);
probed for cost-runaway, memory growth, SSRF, and XSS.

## Findings (confirmed by test) & resolutions

| # | Severity | Finding | Fix shipped |
|---|---|---|---|
| 1 | **HIGH** | Fable-5 code (catchphrase/quirk wiring, per-agent voices, speaker buttons) never persisted to disk last turn — only the census *text* did. The running server was using pre-Fable-5 code. | Re-applied all Fable-5 wiring in this hardened build and verified on disk. |
| 2 | **HIGH** | `master_turn` used `while True` with no cap on tool-use rounds. A looping model could call tools forever → unbounded API cost / hang. | Added `MAX_TOOL_ROUNDS` (12) and a per-turn tool-call budget (`MAX_TOOL_CALLS`, 8). |
| 3 | **HIGH** | `read_webpage` had no SSRF protection — the model could be steered to fetch `http://169.254.169.254/…` (cloud metadata) or internal `localhost` services. | Added URL guard: only http/https, blocks loopback, private, link-local, and reserved IPs after DNS resolution. |
| 4 | **MED** | Malformed `history` item (missing `content`/`role`) raised `KeyError` → HTTP 500 crash. | `sanitize_history()` drops/normalizes bad items and enforces user/assistant alternation. |
| 5 | **MED** | A tool receiving a bad arg (e.g. non-numeric `max_results`) raised `ValueError` **inside** the loop → the entire turn 502'd. | Every tool call wrapped in try/except; safe int coercion; failures become a readable message, turn continues. |
| 6 | **MED** | Fetched web/YouTube content was fed to the model verbatim — a page could contain "ignore your instructions" (prompt injection). | Tool results wrapped in a data-only boundary telling the model not to follow embedded instructions. |
| 7 | **MED** | `JOBS` dict for autonomy missions grew forever (memory leak on a long-lived server). | Prune to the most recent 50; finished jobs evicted oldest-first. |
| 8 | **MED** | XSS/breakage risk in the planned speaker button (inline `onclick` with interpolated agent text — a single quote would break the attribute). | Speaker buttons bind via event delegation + `data-slug`; no interpolated inline handlers. |
| 9 | **LOW** | No request size limit — a 500k-char message was accepted and forwarded to the API. | Message/goal capped at 20k chars with a clear 413-style message. |
| 10 | **LOW** | Autonomy `/api/auto/start` didn't check for the API key — a mission would silently error per step. | Refuses to start with a clear message if the key is missing. |
| 11 | **LOW** | No health/readiness endpoint for monitoring. | Added `GET /api/health` → agents loaded, cast count, key-present, tool availability. |
| 12 | **LOW** | `esc()` in the HUD escaped only `&` and `<`. | Now also escapes `>` and `"`. |

## Not changed (accepted)
- **Dark-glow + single-font HUD aesthetic** — intentional Jarvis look, confirmed by Lev.
- **Localhost-only bind** (`127.0.0.1`) — correct for a personal app; no CORS needed.
- **Threaded autonomy without locks** — CPython GIL makes the dict ops used here safe; a lock was added only around prune.

## Verification
All 12 fixes re-tested green: malformed history → 200, SSRF blocked, tool-round cap holds,
oversized input rejected cleanly, health endpoint reports status, per-agent voices + speaker
buttons render without JS errors, 274/274 agents still cast.
