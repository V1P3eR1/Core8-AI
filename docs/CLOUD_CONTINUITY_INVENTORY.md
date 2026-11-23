# Cloud continuity inventory — proposal (2026-11-22)

**Status: DRAFT / READ-ONLY.** Owner request: run Core8-AI and LEV OS workflows in hosted infrastructure rather than relying on a powered-on desktop or laptop. This document is not evidence of deployment, hosted Claude execution, or approval to modify credentials, permissions, production, or spending.

## Source of truth and safety

- GitHub: code, issues, PRs, CI evidence and immutable release identifiers. Never use a floating feature branch as a production release (#48).
- Notion: business task queue, decisions and synchronized status via the **existing** #15 approval-gated handoff; do not create a second task bridge. Notion connector was reverified on 2026-11-22 using the explicitly selected personal linked account: queue schema and eight rows were readable. This does **not** verify GitHub Actions' separate Notion credential or live write permissions.
- Obsidian: private knowledge vault; encrypted selective synchronization only, never copy the whole vault into this public repository.
- Google Drive/private storage: encrypted, access-controlled backups with restore drills; do not replicate secrets or customer databases into public artifacts.
- LEV personal brand and Core8-AI commercial brand: distinct accounts, assets, permissions, content calendars and lead data.

## Initial component inventory (no runtime assertions)

| Component | Current evidence | Cloud target | Persistent state | Gate / blocker |
|---|---|---|---|---|
| GitHub code and PRs | Existing repository and #15 | GitHub-hosted | Git history and PR reviews | Human review and CI required; branch rules must be verified |
| Claude handoff | `docs/HANDOFF.md`, PR #15 | Approval-gated hosted workflow | Notion queue, GitHub issue, patch artifact | Workflow defaults disabled; owner-approved exact scope, budget, credentials, harmless pilot |
| Core8 platform | `docs/LAUNCH_READINESS.md`, #11 | Approved staging first | Application database and files | Tenant isolation, secrets, release pinning, tested backup/restore |
| Deployment | #48 describes `install.sh` floating branch risk | Pinned immutable release workflow | Release SHA, logs, rollback snapshot | Explicit owner approval per deployment; do not touch VPS |
| Social Manager | #9 / #38 | Hosted worker after security verification | Jobs, assets, approvals, tokens | No multi-tenant rollout until isolation tests pass; external posts remain approval-gated |
| CRM and lead intake | #14 / #31 / #32 | Staging with synthetic data | Tenant-scoped DB and consent records | No live leads or outbound messages without approval |
| Customer demos | #24 / #26 | Static hosted preview when approved | Synthetic fixtures only | Demo labels; no live third-party integration |
| Obsidian private vault | User preference, local paths not inspected | Encrypted private sync | Vault revisions | Owner selects scope/provider; never public Git |
| Notion task queue | Live personal connector read verified 2026-11-22; 8 rows; #17/#20 mapping | Existing hosted Notion | Task approvals and state | Reconnect correct account; validate sync idempotency |
| Backup and monitoring | No verified deployment/runtime inventory in this review | Private encrypted backups, uptime checks | Snapshots, logs, alert routing | Owner chooses provider/retention; test restoration |

## Migration gates and evidence

1. **Inventory** — identify every laptop-only process, cron job, local database, and dependency by *component name*, never secret value. Record current host, owner, data classification, and recovery expectations.
2. **Hosted CI and handoff** — verify #15 workflow permissions, branch rules, disabled-by-default flags and exact-scope approval. A patch artifact is **not** a tested PR. For a docs-only synthetic pilot, require independent PR review + CI.
3. **Staging continuity test** — demonstrate scheduled task completion while both user PCs are offline; capture run URL, commit SHA, failure/retry evidence and deduplication checks. No live accounts or customer data.
4. **Data protection** — encrypted backup/restore drill, documented RPO/RTO and retention; prohibit secret/database mirroring into public repository.
5. **Release gate** — resolve #11 and #48; require explicit separate Lev approval for merge, production deploy, new credentials, permissions and spending.

## First acceptance checklist

- [x] Notion Integration task queue schema and rows read with working personal account; synchronization page title located (full page content review still pending)
- [x] No duplicate bridge or issue created during this audit; existing bridge reused
- [ ] Branch protection and workflow permissions independently checked
- [ ] Harmless hosted run produces a reviewable artifact and link
- [x] Synthetic contract CI and secret-scan passed on commit `a894ae0` (Actions runs 45015660709 and 45015660643); independent human review remains outstanding
- [ ] No production or third-party side effects
- [ ] Backup restore tested with synthetic data
- [ ] Laptop and desktop can be offline without breaking the *approved* hosted test

## Explicitly not authorized

No activation of paid Claude runs, GitHub Actions with elevated permissions, credential changes, deployment, merge, DNS, publishing, customer-data transfer or production operations. Each requires its own approval and verified prerequisites.

References: #11, #15, #24, #38, #47, #48, `docs/HANDOFF.md`, `docs/LAUNCH_READINESS.md`.

## Read-only live reconciliation (2026-11-22)

- The existing Notion Integration task queue schema was fetched through the personal connector; eight rows were read. This is direct provider read evidence, **not** a newly executed sync.
- Notion #17 mapping: `Closed - unverified`; GitHub issue #17 independently confirmed closed. Notion #20 mapping: `Review`; GitHub issue #20 independently confirmed open, with exact-scope digest embedded. A Review state is **not** proof of accepted/tested code.
- Last sync shown by Notion for both: `2026-11-22 08:51 UTC`. No proof yet that the schedule is still running, nor that GitHub Actions can reach Notion now.
- Both cloud CI jobs on commit `a894ae0` passed: [secret-scan #173](https://github.com/V1P3eR1/Core8-AI/actions/runs/45015660643) and [synthetic-contract #3](https://github.com/V1P3eR1/Core8-AI/actions/runs/45015660709).
- Business Notion connection search returned zero Core8 matches, not an authentication error; business workspace access to this specific queue remains unproven.
- **Next non-paid gate:** review sync workflow's actual deployed configuration and a dry-run run log. No workflow execution or secrets are needed to document existing evidence. Actual Notion write round-trip requires separately scoped operational authorization and environment access.
