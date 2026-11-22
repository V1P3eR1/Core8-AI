# Cloud migration execution register — TEMPLATE / UNVERIFIED

**Purpose:** a single evidence-backed register for moving every approved LEV OS and Core8-AI workflow to hosted execution. This is not a live operations status board. Fill only from verifiable provider/repository evidence. Do not put customer data, keys, private vault paths or credentials in this public repository.

## Workflow record schema

| Field | Required value |
|---|---|
| Workflow ID | Stable non-sensitive slug |
| Brand / tenant boundary | `core8`, `lev-personal`, `orchestra-private`, or isolated client ID |
| Accountable owner | Named human or engineering role |
| Runtime | Provider/service and hosted job identifier, or `UNKNOWN` |
| Trigger | Schedule, event, or manual approval |
| State store | Durable queue/database/artifact store, or `UNKNOWN` |
| Inputs / classification | Synthetic, public, internal, restricted (never raw personal data) |
| Allowed tools | Explicit least-privilege list |
| Side effects | None / draft-only / human-approved external action |
| Retry / deduplication | Idempotency key, backoff, maximum retries, dead-letter handling |
| Cost guard | Per-run and monthly limits; `NOT CONFIGURED` if unknown |
| Stop mechanism | Pause flag, kill switch and rollback owner |
| Approval gate | Exact scope, authorized human, expiry and audit reference |
| Recovery | Checkpoint/restart behavior and backup test |
| Evidence | Immutable commit SHA, run URL, test result, timestamp |
| Status | `UNKNOWN`, `LOCAL_ONLY`, `CLOUD_CANDIDATE`, `BLOCKED`, `STAGING_VERIFIED`, `PRODUCTION_APPROVED` |

## Seeded inventory — status is not operational proof

| Workflow ID | Brand | Current status | Existing work | Next evidence |
|---|---|---|---|---|
| `claude-handoff` | core8 | BLOCKED | #15, `docs/HANDOFF.md` | Approved synthetic hosted run; GitHub/Notion gates verified |
| `github-ci` | core8 | UNKNOWN | GitHub workflows; #47 | Fresh main SHA and successful run URLs |
| `release-deploy` | core8 | BLOCKED | #48 | Pinned SHA release design and separate owner deploy approval |
| `social-manager` | core8 | BLOCKED | #9, #38 | Tenant isolation tests and explicit publish approval |
| `lead-pipeline` | core8 | CLOUD_CANDIDATE | #14, #31, #32 | Synthetic end-to-end staging test |
| `customer-demo` | core8 | CLOUD_CANDIDATE | #24, #26 | Static hosted preview, no live side effects |
| `lev-personal-content` | lev-personal | UNKNOWN | Separate brand requirement | Account boundary and draft-only workflow inventory |
| `orchestra-agents` | orchestra-private | UNKNOWN | Private repository (do not export) | Private inventory by authorized owner |
| `knowledge-sync` | all, separated | BLOCKED | #15; Notion connector unavailable | Verify authorized Notion account and selective sync |
| `encrypted-backup` | all, separated | UNKNOWN | Cloud continuity proposal #60 | Owner-selected private provider and restore drill |
| `scheduled-execution-report` | core8 | UNKNOWN | Existing daily automation outside repository | Verify actual schedule/run history and host |

## Safe implementation order

1. Review actual hosted workflows and Notion queue; do not create duplicate tasks.
2. Establish staging-only durable job lifecycle: `QUEUED -> RUNNING -> REVIEW/BLOCKED/FAILED`, with idempotency, bounded retries, timeouts and audit links. No external side effects.
3. Prove one **owner-approved**, docs-only, synthetic run can finish with both user PCs offline.
4. Require independent code review and CI; agent-generated code cannot approve itself.
5. Expand one workflow at a time, after tenant separation, secrets review, recovery test and explicit owner permission for any new cost, production change or external action.

## Acceptance evidence per migrated workflow

- [ ] Provider-hosted job URL and timestamp
- [ ] Durable state survives worker restart
- [ ] Duplicate trigger cannot execute twice
- [ ] Failure and retry behavior tested
- [ ] Approval pauses only dependent job, not unrelated jobs
- [ ] No customer or secret leakage into public logs/artifacts
- [ ] Offline-PC test witnessed and recorded
- [ ] Costs, limits and emergency stop verified
- [ ] Human sign-off and rollback instructions linked

**Hard stop:** no credential creation/rotation, permission change, paid runtime activation, merge, deploy, social publishing, external outreach, payment or DNS change without separate Lev approval. This file only defines a future acceptance process.
