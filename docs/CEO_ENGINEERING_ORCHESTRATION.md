# Core8-AI CEO ↔ Engineering operating system (V1 proposal)

**State:** PROPOSED / NOT ACTIVATED. No new automation enabled by this document.
**Existing authority:** `CLAUDE.md`, `docs/HANDOFF.md`, `tools/handoff/bridge.py`, `.github/workflows/claude-issues.yml`.
**Date:** 2026-11-22.

## Purpose
Lev gives a goal once, to ChatGPT. ChatGPT acts as product/operations CEO: decomposes into linked tasks, prepares customer-safe acceptance criteria, routes through existing approval gates, tracks evidence and reviews results. Claude Code engineers scoped changes in isolated GitHub jobs. No user copying prompts between assistants. This is a **role assignment**, not autonomous authority to approve decisions or spend funds.

## Verified current mechanism (read from main)
- `core8-sync.yml` scheduled every 15 minutes **only when** `CORE8_SYNC_ENABLED=true`; status of variable, credential and actual runs must be checked.
- `claude-issues.yml` listens for authenticated Lev issue comment `/core8-implement <sha256>`, verifies private Notion approval + public-export + exact task digest; requires `CORE8_CLAUDE_ENABLED=true` and protected `core8-claude` environment. Produces untested patch artifact retained seven days, not a PR; no shell/tools for tests.
- Existing customer demo: Issue #24, PR #26; coordination Issue #51. Do not duplicate.
- Agent team definitions: `docs/core8-agents/`, .claude agents & skills exist on main. Do not replace with fictional AG IDs.
- Live production / multi-tenant security and repo privacy must remain separate gate issues (#11, #47, #48, #50).

## Three lanes
1. **Intake (available now):** ChatGPT creates/updates GitHub Issues and reviews PRs using the connected GitHub connector during an active user conversation, with explicit links and idempotent search first. Existing approved Notion queue remains canonical for the current Claude runner; ordinary GitHub issues do **not** automatically authorize execution.
2. **Safe engineering (existing, gated):** Notion approved task + explicit public export + exact Lev GitHub signature -> Claude restricted job -> patch artifact -> manual review. Never auto-approve or confuse issue closure with success.
3. **Proposed enhanced engineering (NOT ACTIVE):** after security review, an isolated worker converts validated patch to a feature branch/draft PR; separate no-secret runner checks lint, tests and screenshots; CEO review records acceptance evidence. No access to production secrets or deploy keys. Not enabled until PR is reviewed and merged with Lev's approval.

## CEO task protocol
Each work item must include:
- project ID, issue ID, owner role, task type, existing dependencies, priority and source version;
- end-user benefit, exact scope and out-of-scope, acceptance criteria, evidence required;
- target demo/staging only, synthetic data, no external side effects;
- `PROPOSED → READY_FOR_REVIEW → APPROVED_BY_LEV → RUNNING → PATCH_READY → TESTED → REVIEWED`, with actual status based only on evidence;
- `BLOCKED` on missing authentication, branch conflict, expense approval, secret or real-user permissions.
Status `DONE` means acceptance evidence and owner review, **not** merely an issue closing or generated patch.

## Governance: no copy/paste path
- ChatGPT receives a request and searches for related issues/PRs. If needed, it creates an issue directly. Lev does **not** re-paste the request.
- If scope requires the approved Notion queue, ChatGPT writes an approved-safe **proposal**, not approval. The scope moves to execution only after the human approval the existing bridge requires.
- For now the user still clicks the exact GitHub approval command **once per authorized scope**; that is a risk control, not a message copied to another agent. Reduce this friction later via a human approval dashboard that signs exact task revisions, instead of weakening the gate.
- Tasks with independent low-risk read-only operations may run on schedules or within ChatGPT automations; no session is continuously running merely because this document exists.
- Claude result is inspected; after patch/PR and separate tests, ChatGPT reports supported status. User approves merges/deployment/costs.

## Phase plan
### Phase 0 — evidence and activation audit
1. Read current `CORE8_SYNC_ENABLED`, `CORE8_CLAUDE_ENABLED` existence (not secrets) via authorized settings/CI observations.
2. Check real action runs, failures, mapping duplication, Notion access. Do not enable or change variables in audit.
3. Inventory active issues/PRs and required reviews, especially #24 #26 #51 #60.
4. Prove current gate from an approved **harmless doc task** with owner approval and an actual run link.

### Phase 1 — zero-copy CEO intake
1. Reuse existing Notion task source and issues; avoid dual authoritative backlogs.
2. Add stable task ID and dedupe by existing issue mapping; improve product-to-engineering decomposition and dependencies.
3. Create PR/Issue status notifications from evidence, not guesses.
4. A daily status automation can summarize GitHub, but does not independently run a live Claude session.

### Phase 2 — testable patch-to-PR worker
1. Fetch artifact by immutable run+artifact id; verify SHA, branch, patch paths, executable permission changes, symlinks and size.
2. Apply patch only in fresh, disposable, unprivileged checkout (no credentials); reject workflow/security/production paths and path traversal; require human review for sensitive areas.
3. Run isolated tests with no provider secrets and no external write tokens; report results even on failure.
4. Push to one feature branch with narrowly scoped credentials and open a **draft PR**, no automatic merge. Limit per-task cost and concurrency.
5. CI branch protection, codeowners/manual reviews, security checks; no shell from untrusted issue body.

### Phase 3 — client showcase
- Build demo preview from reviewed branch using fake clinic / real estate / automotive records.
- Label simulation permanently, record version/SHA, screenshot evidence and tests. Staging or public preview only after explicit authorization.
- Connect live WhatsApp / Gmail / Calendar / Meta only as separate owner-approved security and compliance tasks.

## Explicit non-goals
- No autonomous merging, publishing, contacting customers, billing, production deployments or permission/key rotation.
- No confidential or personal data in this **public** repository.
- Do not infer Claude Code is live or paid execution is enabled from the existence of workflows.
- No merge of different products into a single app simply to simplify task tracking.

## Implemented control-plane pilot (draft PR #61; not activated)

The new `tools/orchestration/dev_loop_health.py` is a deterministic **read-only observer**, not a code-writing agent. It fetches at most 60 open PR heads and their current GitHub check runs, keeps the latest result by check name and run time, identifies failures/pending checks, and emits a bounded `core8-dev-loop-report.json`. It explicitly ignores task bodies and comments as instructions and never uses customer data, API models, external write endpoints or deployment credentials. `tools/orchestration/test_dev_loop_health.py` provides offline synthetic regression coverage.

`.github/workflows/dev-loop-health.yml` runs contract tests for changes to the monitor and proposes hourly reporting on `main`, **only after both** the PR is reviewed/merged **and** an authorized operator explicitly sets `CORE8_DEV_LOOP_ENABLED=true`. Scheduled CI may incur GitHub Actions costs depending on repository plan and quota; do not enable without cost review. A successful PR test does not prove that the future scheduled monitor has run.

### The desired closed-loop state machine

```text
GitHub/Notion state reconciliation (existing sync, approval required)
  → read-only inventory and CI failure detection (new observer)
  → choose one existing scoped task or a failing PR (no duplicate issues)
  → signed scope + budget approval (existing human gate)
  → Claude Code bounded patch generation (existing gated workflow, usage may cost)
  → proposed isolated patch validation + disposable tests (NOT implemented)
  → draft PR + CI + security review (NOT automated)
  → fix/retest up to a bounded retry count (NOT automated)
  → evidence-based report + next task (read-only report available)
  → merge/deploy remain separate explicit owner approvals
```

**Operational rule:** don't claim an automated repair happened merely because the monitor says `review_ci_failure`. In V1 that status is advisory and routes to the existing gated engineering lane. The missing patch-to-PR worker, retry control and automatic acceptance/replanning are implementation gaps, not features currently running.

### Implemented structural patch admission (draft; not an executing worker)

The new `tools/orchestration/validate_patch.py` accepts only small UTF-8 reviewable text patches scoped to `apps/` or `docs/`. It rejects potential credentials, workflows, deploy scripts, environment files, executable/symlink/submodule modes, renames, binary patches, path traversal, duplicate files and oversized changes. Offline adversarial tests run in the same read-only CI workflow.

**Security warning:** the structural validator is **not a full Git patch parser, not a sandbox and not a proof of safety**. It does not apply a patch, verify hunk counts, prevent runtime malicious changes in otherwise allowed files, run tests or authorize a draft PR. A future worker must additionally verify the actual filesystem diff after applying in a sandbox, compare changed paths to the approved task scope, conduct code/security review, and use narrowly scoped write credentials separate from the execution sandbox.

### Implemented retry decision policy (draft PR #61)

`tools/orchestration/retry_policy.py` adds a pure, fail-closed policy for the **next recommended engineering action**; it does not call a model or run patches. The policy validates exact task/scope digest, owner-approved current commit SHA, real CI failure state, chronological same-scope attempt history, explicit paid-execution permission, a 30-minute cooldown and a hard limit of two attempts. Green checks move to human review rather than triggering another patch. Exhausted retries or changed SHA stop for re-approval. Its decision output permanently sets `execution_authorized=false` and `may_spend=false`; even `propose_approved_patch_lane` is **only a proposal**, not approval to spend or invoke Claude.

Offline cases in `tools/orchestration/test_retry_policy.py` cover missing approval, stale heads, missing/pending CI, retry exhaustion, cooldown, nonfailed attempts, mismatched history and time validation. The hourly observer currently **does not call this policy automatically** because it lacks an authenticated, durable, owner-approved task/attempt ledger. Connecting this policy to Notion/GitHub must be a separately reviewed step that proves source integrity, idempotent run claims and tamper-resistant event records. Never auto-populate `approved=true` from PR labels or issue comments.

### Deterministic attempt ledger — implemented, but not a live coordination backend

`tools/orchestration/attempt_ledger.py` now models a bounded two-attempt execution history using strict hash-chained events and replay. It refuses duplicate claims, concurrent starts for the same scope, invalid event sequences, changed history, backward timestamps, unrecognized fields and retry after success or cancellation. `history_for()` creates an audited in-memory input for the pre-existing `retry_policy.decide()` policy. Adversarial synthetic tests live in `test_attempt_ledger.py` and are covered by the orchestration CI workflow.

**Not running in production:** This is a pure offline fixture/module with no persistent shared ledger, no locking across GitHub jobs, no distributed single-writer guarantee and no authenticated actor signature. A SHA-256 chain detects edits only relative to a previously trusted head hash; it does not authenticate the writer or stop complete log replacement. It must not be treated as evidence of owner approval. No automatically generated patch is executed or merged as part of this implementation.

**Next safe engineering tasks:** introduce a verified durable attempt record tied to GitHub run ID and immutable approved scope, atomic idempotency claims across concurrent runners, recorded model budget consumption, redacted failure evidence, a separately sandboxed patch review workflow, and a human review gate before any PR is merged. Preserve the existing owner/Notion approval mechanism rather than allowing the ledger to grant permissions.

### November 23 — private Notion ↔ GitHub reconciliation contract (draft)

The connected private Notion integration was used to **read**, not export, the existing nine Core8 integration tasks. A material observation: the Finance OS task formerly shown as `In progress` now reads `Awaiting approval`, with `Public export=false`; its existing GitHub Issue #63 remains linked. This is a **status discrepancy requiring review**, not permission to overwrite Notion or revive a task in GitHub. Historic reports in this document are snapshots and must not be used as current approval evidence.

`tools/orchestration/notion_reconciliation.py` and its synthetic tests implement a standalone, **read-only comparison** of pre-fetched private Notion task metadata and GitHub issue snapshots. It verifies task IDs, unique issue mapping, exact task markers in issue bodies, actual issue open/closed state and the separate Notion public-export/approval-evidence gates; it refuses invalid domains and duplicated mappings. Output contains only task IDs, issue numbers, status and fixed diagnostic codes. Private `Scope`, `Acceptance`, approval evidence URLs and user details never appear in the report. It does not automatically import customer data, create GitHub issues, update Notion properties or authorize Claude.

**Remaining gap:** the hourly workflow currently fetches GitHub check runs only; it does not retrieve private Notion tasks because the private connector credentials must not be put into a public-repository CI context without a reviewed design. Cross-source reconciliation is a tested library contract, **not an activated scheduled sync**. Verified source identity, isolated secrets and an explicit write approval gate must precede any live status updates.

### Human-readable engineering report artifact (added in draft)

`tools/orchestration/dashboard_report.py` now renders a bounded, Markdown-safe management summary from the pre-existing read-only GitHub CI report. It shows per-PR current head SHA, failure/pending/incomplete evidence status, sanitized check names and links, with no AI execution or approval capabilities. Optional *pre-audited* Notion reconciliation metadata may be summarized as **counts only**, not private Scope/Acceptance/task identifiers. Tests cover untrusted Markdown/HTML injection, duplicate PRs, invalid states, private task data omission and fail-closed schemas. The scheduled `observe` job is configured to attach both `core8-dev-loop-report.json` and `core8-dev-loop-report.md` when explicitly enabled after approved merge.

**Limitations:** no live Notion reads in GitHub CI, no customer data, no persistent dashboard service, no feedback writes to the Notion source, and no running engineering agent. A passing contract job on the draft PR only verifies local synthetic tests, *not* successful scheduled reporting.

### Offline Hebrew browser dashboard (PR #61, November 23)

`tools/orchestration/browser_dashboard.py` now converts the sanitized GitHub check snapshot to a standalone, RTL Hebrew `core8-dev-loop-dashboard.html` report. It has a responsive count summary, PR links, current head SHA and CI states, no JavaScript, no network-dependent CSS/assets and a restrictive content security policy. Untrusted check names are HTML-escaped and capped. **Private Notion fields never enter this HTML report**. Synthetic privacy/injection and malformed-input tests live in `test_browser_dashboard.py`.

The explicitly approved and merged `observe` job, **if** later enabled via `CORE8_DEV_LOOP_ENABLED=true`, would upload three read-only artifacts: JSON, Markdown and HTML. This PR's own pull-request run executes synthetic contract tests only, so no live dashboard artifact should be claimed before a post-merge observation actually runs. To view it when activated, open the relevant GitHub Actions observation run, download `core8-dev-loop-report`, and open the HTML file locally. No hosting, user login, production API, automatic PR execution or status mutation has been activated.

### Bounded live repository-wide snapshot (draft PR #61)

The `repo-wide-preview` CI job on the explicitly trusted same-repository orchestration branch reads the current GitHub list of open PRs and their head-SHA check runs, **up to 20 PRs**, without using Notion, paying for AI, editing issues or deploying. It emits separate JSON, Markdown and offline RTL HTML files as `core8-dashboard-REPO-LIVE-SNAPSHOT` in the PR's GitHub Actions artifacts. It validates metadata and refuses ambiguous/truncated check pages. If the PR listing exceeds the cap, both dashboard formats explicitly flag **partial coverage** rather than claiming to show every active PR.

This job is a **point-in-time snapshot**, not an authenticated live SaaS dashboard or persistent monitoring process. The PR itself remains a draft and the scheduled main-branch observer remains separately gated by `CORE8_DEV_LOOP_ENABLED`. GitHub CI checks, Notion approvals, production deployments and customer tenancy must remain distinct security boundaries.

### Safe activation checklist

1. Inspect this PR diff and successful `Core8 development loop (read-only)` CI, security review, codeowners and actions-policy compatibility.
2. Obtain separate user approval for merge; do **not** merge simply to turn on scheduling.
3. Establish whether running hourly GitHub Actions will cost money under the repository's current billing plan.
4. Obtain separate owner approval to set `CORE8_DEV_LOOP_ENABLED=true`, initially for an observation-only pilot.
5. Verify two successive report artifacts show current PR head SHAs, no customer data and correct priority, without duplicated issues or writing to GitHub.
6. Only after independent approval add a worker that consumes an immutable patch with signed scope, explicit retry and dollar caps, failure isolation and draft-only PR creation; do not reuse provider secrets in jobs that execute agent-generated code.
7. A human reviews and authorizes any merge, production deploy, API spending or public communication.

### Why this approach

GitHub Actions supports reusable gated pipelines, scoped token permissions and concurrency; coding agents can be called by GitHub Actions, but secret management and untrusted PR/issue input require isolation. The existing `claude-issues.yml` already handles approvals and generates patch artifacts. The observer reuses that lane rather than inventing a second, unsafe autonomous writer.

References: GitHub Docs, agentic workflows (https://docs.github.com/en/actions/tutorials/develop-agentic-workflows-in-github-actions); GitHub concurrency and permissions (https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations); Codex CI auto-fix (https://developers.openai.com/cookbook/examples/codex/autofix-github-actions); Anthropic Claude Code Action (https://github.com/anthropics/claude-code-action/blob/main/docs/usage.md).

## Immediate handoffs (do not duplicate)
- Demo: [#51](https://github.com/V1P3eR1/Core8-AI/issues/51) and [PR #26](https://github.com/V1P3eR1/Core8-AI/pull/26)
- Security: [#11](https://github.com/V1P3eR1/Core8-AI/issues/11)
- Cloud continuity: [PR #60](https://github.com/V1P3eR1/Core8-AI/pull/60)
- This orchestration proposal must not overwrite existing workflows before a reviewed, tested follow-up PR.

## Definition of done for an operational V1
1. Two successive task creations map once to distinct GitHub issues without human prompt copying.
2. A benign task passes all existing owner approval gates and yields a real Claude run/patch link.
3. A separate tested PR is produced **only** in authorized draft mode; all actions recorded.
4. At least one end-to-end offline demo is opened and visually checked, and its limitations shown.
5. Owner can stop new work and cancel active runs; costs are bounded, with no secrets leaked or production mutations.
