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
