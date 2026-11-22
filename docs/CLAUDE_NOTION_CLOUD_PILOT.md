# Claude + Notion cloud pilot — preflight and runbook (NOT ACTIVATED)

**Authorization:** Lev approved preparing a real cloud pilot on 2026-11-22, but **did not approve paid-service activation**. This document prepares the existing #15 bridge, not a replacement. No credentials, runtime, workflow variables or permissions were changed.

## Verified from repository

- `docs/HANDOFF.md`: existing architecture and manual activation procedure; Notion owns task scope/decisions; GitHub owns issues, approval comments, audit and patch artifacts.
- `.github/workflows/claude-issues.yml`: existing gated Claude workflow; job gate requires `CORE8_CLAUDE_ENABLED=true`, matching numeric human `CORE8_APPROVER_ID`, exact `/core8-implement <SHA256>` comment, and a non-PR issue. Separate `core8-sync` and `core8-claude` environments.
- Claude action currently has `--max-turns 6`, `--max-budget-usd 0.25`, model haiku and restricted Read/Edit/Write/Glob/Grep tools. **This is a per-run argument, not a verified account-level spend cap.**
- Notion connector access from the ChatGPT session was previously unavailable. Actual Notion data-source ID, provider credentials, enabled flags, environment protections and live execution are **not verified**.
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
| Notion queue live read/write | UNKNOWN | Reconnect correct Notion linked account |
| Sync workflow live readiness | UNKNOWN | Identify actual workflow and inspect |
| Branch protection enforced | UNKNOWN | Verify in repository settings |
| Protected environments and credentials present | UNKNOWN | Check presence only; no secret exposure |
| Synthetic Notion/GitHub round trip | NOT RUN | Separate activation approval |
| Paid Claude patch run | NOT AUTHORIZED | Separate owner approval required |
| Both PCs off continuity | NOT TESTED | Hosted run evidence |

## Fail-closed rules

Do not publish private Obsidian content, actual customer records, credentials, personal plans or unreviewed Notion pages into the public Core8-AI repository. Do not enable flags, change permissions, configure secrets, initiate Anthropic billing, merge, deploy or publish on the basis of this preparation authorization. A GitHub Actions green synthetic test is not proof of Notion integration or paid Claude execution.
