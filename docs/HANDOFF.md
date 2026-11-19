# Core8 handoff MVP

Status: implemented for review, **disabled pending Lev's activation approval**.
No deployment, merge, secret configuration or paid Claude run is performed by
creating this PR. This replaces the proposed orchestration in PR #12; do not
merge both implementations of `claude-issues.yml` unchanged.

## Ownership and flow

1. ChatGPT reads the main Notion synchronization page before strategy work. It
   writes a task directly into its Integration task queue through the connected
   Notion tool. Lev does not copy messages into Claude.
2. Notion owns scope, acceptance criteria, decision classification and consolidated
   status. `Proposal` is the default convention. Models must not set `Approved`
   without explicit Lev evidence. `Public export` is a separate privacy review.
3. The deterministic bridge exports only Name, Scope and Acceptance plus an opaque
   task ID. It never exports page bodies, discussions, approval links or the main
   strategy document. GitHub owns code and execution evidence.
4. Eligible tasks become public GitHub issues, with a SHA256 of canonical scope.
   Lev posts the displayed `/core8-implement SHA256` approval in that issue.
   This is an approval action, not copying a specification between assistants.
5. The gate verifies the configured numeric human GitHub identity, current comment,
   current Notion decision, exact task revision, queue membership and exact issue
   body/title. A label or a model-written approval cannot start implementation.
6. Claude edits only a disposable checkout. The minimum pilot exposes Read, Edit,
   Write, Glob and Grep tools; no shell tools. The GitHub token is read-only and
   the job has no Notion or production credential. It returns an apps/docs patch
   artifact, not a production change or a merged commit.
7. A separate clean job records fixed status events and a run link in the issue.
   The next sync mirrors Queued / In progress / Review / Blocked into Notion.
   Review means an untested patch exists. A closed issue becomes Closed - unverified,
   never automatically Done. Acceptance, tests and eventual PR/merge remain human
   review steps. This pilot deliberately does not execute generated code with keys.

## Task schema

| Property | Owner / meaning |
|---|---|
| Name, Scope, Acceptance | ChatGPT/product; public-safe execution specification |
| Decision | Proposal / Approved / Rejected, backed by Lev evidence |
| Approval evidence | Private source URL proving the business approval |
| Public export | Explicit review that the three exported fields may be public |
| Task ID | Notion-generated human identifier; page UUID is machine identity |
| GitHub issue, Sync digest | Bridge-owned mapping and exact revision |
| Status, Last sync, Sync error | Bridge-owned observed state, freshness and fixed error code |

Private reasoning stays in the task page body. Do not paste credentials anywhere
in Notion, issue bodies, comments, logs, prompts or patches. Secret-pattern checks
are defense in depth, not proof that prose is safe or a DLP guarantee.

## One-time activation (Lev approval required)

- Review this PR; reconcile/supersede PR #12. Configure actual protection/rulesets
  for main: required human review and CI, no agent bypass. On audit main reported
  `protected: false`; instructions alone do not enforce protection.
- Create GitHub environment `core8-sync`. Store a dedicated `NOTION_TOKEN` there,
  granting read/update access only to the task queue. Keep this credential out of
  the Claude environment. Existing ChatGPT connector authentication cannot be
  extracted or reused as an Actions secret.
- Set repository variable `NOTION_DATA_SOURCE_ID` to the queue's data-source UUID
  (not its database/page UUID). Set `CORE8_APPROVER_ID` to Lev's verified numeric
  GitHub user ID. Do not authorize a bot or a broad collaborator role.
- Create environment `core8-claude`, required reviewer Lev, restrict to main;
  put a separate budget-limited `ANTHROPIC_API_KEY` there. The explicit read-only
  github_token avoids relying on a broader Claude App token. Validate Anthropic
  account/API access and cost limits separately; no values belong in documents.
- Merge only after review. Initially keep both `CORE8_SYNC_ENABLED` and
  `CORE8_CLAUDE_ENABLED` absent/false. Enable sync after approval, manually run it
  with apply=false, inspect the metadata-only plan, then run apply=true for a
  harmless documentation task. Scheduled runs apply every 15 minutes thereafter.
- Verify the mapped issue, repeat sync (no duplicates), and verify Notion status.
  Then enable Claude, approve the harmless task's exact hash, approve the protected
  environment job, inspect its patch, and confirm Review plus run link round-trip.
- Do not treat mocked tests as live integration proof. Record the first successful
  run link in Notion. Check stale Last sync and failed Actions notifications.

## Failure, concurrency and audit

Only one sync runs at a time; Claude jobs serialize per issue. The scope UUID is
embedded in the issue so a retry recovers after issue creation but before Notion
mapping succeeds. More than one match blocks; human edits are never overwritten.
Changed scope requires a new Notion task revision; keep and link the old task.
The bridge does not automatically close/delete issues or erase audit history.

A machine `started` comment claims a scope at most once. Duplicate comments and
workflow reruns cannot spend again. Failed or uncertain attempts require a new
task revision and fresh approval. GET requests have bounded transient retries;
ambiguous writes fail instead of risking duplicate side effects. Next sync repairs
mapping. External deletion of issue markers/audit comments defeats this convention;
it is an operational audit trail, not immutable or tamper-proof storage.

GitHub comments retain scope digest, state and run URL. Notion retains status and
source links; GitHub Actions retains run history and the patch for seven days.
No free-form logs or AI output are copied into Notion. Unknown errors fail closed
with fixed reason codes, without response bodies or credential values.

Disable both ENABLED variables to stop new work; cancel active runs separately.
Revoking a Notion decision blocks future starts, but cannot undo an in-flight
Claude attempt. Cancel the run to stop it. The protected environment approval
is an additional guard; the initial gate is not an atomic cross-service transaction.
An interrupted run can remain In progress: inspect its run link before retrying.
Unchecking Public export does not retract already public content.

## Verified audit and limits

- Notion read/write and GitHub read/write connectors are available in this chat.
  They are session tools, not a daemon. ChatGPT cannot watch every future chat,
  initiate itself on a PR, or write intake without an active authorized tool call.
- Main contains test and secret-scan workflows; PR #12 proposes Claude execution
  but was open at audit. No active cloud Claude runtime or credentials verified.
- No local Claude CLI was found in this workspace's PATH. This workflow does not
  address or control an already-running Claude desktop/local conversation.
- Notion's Approved/approval URL/Public export fields are a human governance
  convention, not authenticated proof of who clicked them. Restrict queue editing
  to trusted editors. Implementation additionally requires authenticated GitHub
  approval. A stronger publication gate is future work if more editors join.
- Sync polls; it is not instant and GitHub schedules may be delayed. It covers only
  this queue and fixed cloud run states, not every historical issue, arbitrary local
  Claude progress, every PR or all free-form sections of the main document.
- Existing historical decisions are summarized in Notion with provenance; prices,
  annual plans, billing terms, CRM selection and production rollout remain proposals
  unless separately approved. We do not infer approval from a code branch or model.
- No Drive mirror is implemented. No production deployment, autonomous publication,
  payments, secrets rotation, customer data writes or automatic merges are included.
- A cloud patch is a review deliverable. Automatic PR publication and running tests
  on agent-generated code in an isolated no-secret job are potential next steps.

## Validation and references

Run `python -m unittest discover -s tools/handoff -p 'test_*.py' -v` (standard
library only). Tests cover proposals, privacy opt-in, missing approval, replay,
partial failure, conflicts, secrets, forged status/approvals, scope changes and
revocation. No production backend changes are needed for this bridge.

- [Notion data source query API](https://developers.notion.com/reference/query-a-data-source)
- [Claude action inputs](https://github.com/anthropics/claude-code-action/blob/main/action.yml)
- [GitHub workflow trigger restrictions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)

The implementation does not rely on bot-created issue events triggering another
workflow. Only Lev's actual approval comment starts the gated Claude lane.
