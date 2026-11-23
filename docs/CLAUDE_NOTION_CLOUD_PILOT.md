# Claude + Notion cloud pilot — preflight and runbook (NOT ACTIVATED)

**Authorization:** Lev approved preparing a real cloud pilot on 2026-11-22, but **did not approve paid-service activation**. This document prepares the existing #15 bridge, not a replacement. No credentials, runtime, workflow variables or permissions were changed.

## Verified from repository

- `docs/HANDOFF.md`: existing architecture and manual activation procedure; Notion owns task scope/decisions; GitHub owns issues, approval comments, audit and patch artifacts.
- `.github/workflows/claude-issues.yml`: existing gated Claude workflow; job gate requires `CORE8_CLAUDE_ENABLED=true`, matching numeric human `CORE8_APPROVER_ID`, exact `/core8-implement <SHA256>` comment, and a non-PR issue. Separate `core8-sync` and `core8-claude` environments.
- Claude action currently has `--max-turns 6`, `--max-budget-usd 0.25`, model haiku and restricted Read/Edit/Write/Glob/Grep tools. **This is a per-run argument, not a verified account-level spend cap.**
- The personal Notion connector was verified on 2026-11-22: the Integration task queue schema and 8 rows were read. Its data-source ID is `abbb517c-da0c-4913-be23-d85bba4d135d` (non-secret schema identifier). This does **not** establish that GitHub Actions has its own Notion token, that any enabled flag is true, or that live writing works. The business connector returned no matching Core8 results.
- No new provider account or paid action is authorized by this runbook.

## Phase A — read-only readiness (safe now)

1. Verify repository default branch and whether main protection/rulesets enforce human approval, CI and no bypass.
2. Locate existing Notion synchronization workflow and confirm its exact filename, permissions, schedule, concurrency, default-off variables and scope; do not create a duplicate.
3. Verify that the Notion Integration queue is accessible from the intended linked account. Confirm only the *data-source ID* (not the page/database ID), property schema and minimal integration scope. Do not paste IDs or secrets into public issues.
4. Confirm environments `core8-sync` and `core8-claude` exist with required reviewers and correct branch restrictions. Check variable names and whether secrets are configured **by presence only**; never expose values.
5. Record each check as PASS / FAIL / UNKNOWN with evidence URL and date. UNKNOWN blocks activation.

## Phase B — owner setup (requires distinct permission; no paid service yet)

1. Owner reviews Notion workspace access and chooses the authorized queue. Create dedicated integration credential with queue-only read/update rights, stored as `NOTION_TOKEN` in protected `core8-sync` environment.
2. Owner configures `NOTION_DATA_SOURCE_ID` and verified `CORE8_APPROVER_ID` as repository variables, then reviews protected environments and branch protection.
3. Keep `CORE8_SYNC_ENABLED=false` and `CORE8_CLAUDE_ENABLED=false` until the separate approval to activate each workflow.
4. Review metadata-only sync in dry-run (`apply=false`) before any public export. Notion task title/scope/acceptance must be fictional and public-safe.

## Phase C — synthetic Notion ↔ GitHub proof (requires owner activation approval)

- Create one fictional documentation-only Notion task with exact acceptance criteria, `Proposal` status initially, and explicit `Public export` review.
- Run dry-run sync; inspect proposed issue, digest, privacy and duplicate detection. Then owner approves actual export.
- Run apply; capture GitHub issue link, sync timestamp and digest; repeat sync and verify exactly one issue.
- Mirror `Queued` / `Blocked` safely; do not infer human approval from a model-authored field.
- Stop here before Claude: this phase does not require `ANTHROPIC_API_KEY` or paid model execution.

## Phase D — Claude patch pilot (requires **separate paid-service approval**)

- Owner sets account-level budget cap and separate `ANTHROPIC_API_KEY` in `core8-claude`, with required human environment review.
- Owner explicitly approves the **exact task digest** in GitHub, then separately approves the protected job.
- One synthetic docs-only Claude patch runs in disposable checkout, with no shell, deployment, customer data or production credentials.
- Verify artifact, logs, scope, cost, issue state and Notion status. Generated patch is **untested** until independent PR + CI. Do not merge or deploy automatically.
- Record cloud run URL and repeat/offline-PC test. Disable flags and cancel runs if abnormal.

## Required go/no-go evidence

| Gate | State at authoring | Evidence / action |
|---|---|---|
| Existing Claude gate inspected | PASS (static code) | `.github/workflows/claude-issues.yml` |
| Existing architecture inspected | PASS (static docs) | `docs/HANDOFF.md` |
| Notion queue live read | PASS | Personal Notion connection: schema + 8 rows on 2026-11-22; no write attempted |
| Notion queue live write | NOT TESTED | Requires separately authorized safe write |
| Sync workflow static inspection | PASS | `.github/workflows/core8-sync.yml` on main; cron every 15 minutes, default-off gate and manual dry-run |
| Sync workflow live readiness | UNKNOWN | Separate GitHub Actions environment credentials and enabled flag unverified |
| Branch protection enforced | UNKNOWN / BLOCKED | GitHub branch protection GET returned 403 to this integration; repository rulesets GET returned `[]` (no visible rulesets). Do not assume protection |
| Protected environments and credentials present | UNKNOWN | Check presence only; no secret exposure |
| Synthetic Notion/GitHub round trip | NOT RUN | Separate activation approval |
| Paid Claude patch run | NOT AUTHORIZED | Separate owner approval required |
| Both PCs off continuity | NOT TESTED | Hosted run evidence |

## Fail-closed rules

Do not publish private Obsidian content, actual customer records, credentials, personal plans or unreviewed Notion pages into the public Core8-AI repository. Do not enable flags, change permissions, configure secrets, initiate Anthropic billing, merge, deploy or publish on the basis of this preparation authorization. A GitHub Actions green synthetic test is not proof of Notion integration or paid Claude execution.

## Verified preflight update — 2026-11-22

- **Exact workflow discovered:** [`.github/workflows/core8-sync.yml`](https://github.com/V1P3eR1/Core8-AI/blob/main/.github/workflows/core8-sync.yml). Runs on `workflow_dispatch` (input `apply=false` by default) or schedule `*/15 * * * *`, but its job runs only when `vars.CORE8_SYNC_ENABLED == 'true'` on `main`. It uses `core8-sync` environment, `NOTION_TOKEN` secret, `NOTION_DATA_SOURCE_ID` variable, read-only contents and issue-write permissions, with concurrency serialization.
- **Operational warning:** Once enabled, *scheduled* sync uses `APPLY=true` automatically. Thus enabling the flag is **not** merely a harmless read-only test: eligible tasks can be exported to the public GitHub repository and Notion status can be updated. Do not enable until privacy and authorization are independently verified.
- **No duplicate bridge needed:** Existing `tools/handoff/bridge.py` supports `sync` without `--apply` for zero-write dry-run, and `--apply` for writes. The offline contract tests are now included in PR #60's hosted synthetic workflow.
- **Hosted test evidence:** [synthetic contract #4](https://github.com/V1P3eR1/Core8-AI/actions/runs/45016940036) and [secret-scan #179](https://github.com/V1P3eR1/Core8-AI/actions/runs/45016940072) both passed for commit `904dba5`. These are *not* live Notion sync runs.
- **Protection visibility:** GitHub integration cannot read `main` branch protection (403), and rulesets endpoint returned an empty list. This is a governance blocker to merge/activation, not evidence of safe protection.
- **Historical mapping:** GitHub issue #17 is closed and Notion maps it to `Closed - unverified`; #20 is open and Notion maps it to `Review`. Both rows showed last sync `2026-11-22 08:51 UTC`. No fresh cross-service write was attempted.

### Owner-free next steps

Continue static and hosted offline checks, review-only PR updates and evidence collection. Do **not** turn on `CORE8_SYNC_ENABLED`, even temporarily, because the scheduled trigger applies changes. Do not start paid Claude, create or expose public tasks, merge or deploy. Owner-only tasks remain branch protection, protected environments, GitHub Actions token/variable setup and explicit activation.

## Latest hosted evidence and integration boundary — 2026-11-22

- [Cloud continuity #10](https://github.com/V1P3eR1/Core8-AI/actions/runs/45020444185): **PASS**, including the offline synthetic and bridge-contract steps (job step conclusions independently checked).
- [Secret scan #248](https://github.com/V1P3eR1/Core8-AI/actions/runs/45020444207): **PASS**. Latest PR branch commit `73a6ab1` adds independent-process contention coverage; an addressed review thread was resolved.
- **Current Notion connector limitation:** A later access probe from this ChatGPT session returned `link_id must identify an eligible linked account` for both previously used connection identifiers. This is a session connector eligibility error, **not** proof that the Notion page was deleted, that a different chat cannot access it, or that the GitHub-hosted bridge is broken. Avoid instructing the owner to repeat connection changes solely on this evidence. No Notion writes were attempted.
- **Next executable scope without owner action:** keep PR review-only, run offline CI, inspect logs and resolve code-review findings. Live Notion write, paid Claude execution, main merge and deployment remain separately gated.

## Notion connector incident triage — 2026-11-23

**Observed:** `notion_get_self({})`, `fetch(LEV OS page ID)`, and `search('LEV OS')` all fail with the identical error `link_id must identify an eligible linked account`, before any page response. Previous personal and business link identifiers also failed. This points to ChatGPT-side linked-account eligibility/routing, **not** a proven Notion page ACL, deletion, token failure in GitHub Actions, or bridge code defect. No writes or account changes were made.

**Separate fault domains and recovery:**

1. **ChatGPT connector routing:** First use `notion_get_self({})` to establish the current account. If it returns the eligibility error, stop page-level retries; they cannot establish page permissions. Escalate connector eligibility to the integration/provider layer with the exact error and timestamp, without publishing account identifiers or credentials. Other chats having worked previously does not establish this session's eligibility.
2. **Notion workspace authorization:** Only after identity succeeds, fetch the target page by its exact ID and inspect workspace/parent. An actual `object_not_found` at that point may be an ACL or workspace mismatch; do not conflate it with connector eligibility.
3. **GitHub-hosted bridge:** Independently verify `core8-sync` environment and `NOTION_TOKEN` presence (never values), the configured data-source ID, and a **manual dry-run**. ChatGPT's Notion connection does not supply GitHub Actions secrets. Do not enable `CORE8_SYNC_ENABLED` for diagnostics because cron runs apply mode.
4. **Proof of recovery:** identity succeeds; target page fetch succeeds; approved public-only queue schema is readable; dry-run produces zero writes; then separately approved fictional-item apply is audited. Mark each separately PASS/FAIL/UNKNOWN.

**Current recovery state:** ChatGPT connector routing FAIL; page-level access UNKNOWN; GitHub Actions live Notion credential readiness UNKNOWN; hosted offline contract tests PASS. No user reconnection requested on the basis of this error alone.
