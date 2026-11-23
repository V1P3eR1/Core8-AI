# Integrated offline review gate — draft only

**Status:** tested local *preparation*, not a cloud executor, authorized GitHub fetcher or draft PR publisher.

This consolidates proposals PR #65 (strict patch structure), #68 (artifact receipt metadata), #72 (atomic local reservation) and adds a single no-secret `git apply --check` integration layer.

```bash
python -m unittest discover -s tools/handoff -p 'test_*.py' -v
```

What it does: validates independently supplied task/run/artifact details, validates SHA256 and patch structure, checks git applicability without applying, then reserves a unique run/artifact key in a persistent SQLite file. Does not modify the checkout or execute patch content.

**Limits / NOT DONE:**
- Caller must authenticate live run/artifact and human approval through independent trusted channels; a forged `expected_record` defeats the gate.
- The disposable checkout is provided by caller and must itself be pinned to an immutable trusted SHA, isolated from private credentials, network side effects and untrusted repo configuration. This module does not provision or trust the checkout.
- SQLite is safe for local concurrency on shared disk, not a cross-runner cloud durable lock when workspaces are ephemeral.
- No remote GitHub write, no branch/PR creation, no artifact download, no CI execution of generated code.
- Before production use: full git object/worktree audit, malicious patch fuzzing, checked checkout SHA, atomic durable reservation state, recovery/reconciliation for uncertain remote writes, least-privileged GitHub writer and human approval.
- PR remains draft; no activation, merge, paid Claude run, external publishing, or production changes.

Track in Issue #62, review in PRs #65, #68, #72.

## GitHub metadata provenance (read-only proposal)

`tools/handoff/github_provenance.py` independently fetches workflow-run and artifact **metadata only** over authenticated GitHub GET requests and rejects wrong repo/workflow/commit/run identity. It intentionally returns `archive_sha256` for the uploaded GitHub Actions artifact ZIP. **This is not the extracted patch digest**. A future downloader must validate the archive bytes against `archive_sha256`, bound extraction size and paths, then derive the separate extracted patch SHA-256 and bind it to the human-approved task/run before allowing patch validation. The provider metadata alone does not prove Notion approval or user identity; those remain independently gated. This code is not an active job and currently has no live Notion task queue available for approval verification.


## Read-only GitHub issue and comment scope evidence

`tools/handoff/approval_evidence.py` uses the existing read-only GitHub adapter's fixed GET endpoints to verify exact issue/comment IDs, comment author ID/type, unedited single approval command, original issue-body SHA-256 and exact task UUID and scope digest. Unknown numeric identifiers and edited/foreign comments fail closed. Fourteen adversarial/offline tests exercise the evidence boundary.

The expected issue-body digest must come from an independently authenticated canonical Notion task and the existing protected human gate. GitHub comments and issue bodies alone are **not** equivalent to Notion approval; a caller-provided digest is not authoritative. This adapter also does **not** yet prove which issue_comment initiated a particular Actions run: the trusted gate must bind the immutable comment ID, scope revision and workflow run ID, and re-check current Notion approval, before any publication. The present code is offline review-only and is not wired into a privileged workflow.


## Protected-gate to run provenance binding (offline only)

The new `tools/handoff/evidence_binding.py` takes independently fetched read-only
GitHub issue/comment evidence, verified GitHub run/artifact metadata, and an
EXTERNALLY AUTHENTICATED record from a separate protected gate. It rejects
missing, extra, mismatched or ill-typed gate fields; mismatched approval
comment ID, approver ID, task UUID/revision/digest, issue-body digest,
run ID, artifact ID or checkout SHA; and invalid or expired chronology.
It returns `BOUND_FOR_REVIEW_ONLY`, never publication authorization.

**Critical limitation:** a Python dictionary supplied as protected_gate
cannot prove its own origin. The caller must verify the origin and integrity
of the immutable protected record and re-check live Notion task approval.
GitHub Actions run metadata alone does not identify the triggering comment ID.
This module must never be exposed as an authorization endpoint or used to
unlock Claude payments, a privileged writer, merges or deployments.


## Approval-comment chronology (2026-11-23)

Read-only GitHub approval evidence now includes the provider-authenticated
`comment_created_at`. Review evidence binding enforces the order

`protected_gate.approved_at <= verified_comment.created_at <= artifact.created_at <= now < artifact.expires_at`.

This rejects delayed or replayed approval comments associated with an older
artifact, plus missing, ambiguous, or offset-encoded comment times. The
protected gate's schema remains strict: the independently verified comment
timestamp stays with the GitHub evidence, not inside the gate record.

**Operational prerequisite:** the value `protected_gate.approved_at` must
represent a trustworthy private approval timestamp, no later than the GitHub
approval comment. Do not substitute the timestamp of a later Notion re-read
or an arbitrary operator-provided field. These chronology checks are
review-only evidence and cannot substitute for independent authenticity
of the protected gate or live Notion approval.


## Protected-gate authenticity verifier (2026-11-23)

The review-only module at tools/handoff/authenticated_gate.py accepts an
independently supplied **canonical UTF-8 JSON receipt**, a lower-case hex
HMAC-SHA256 signature and a separately provisioned verifier key. It authenticates
bytes with constant-time signature comparison and purpose separation, rejects
noncanonical JSON, duplicate object keys, oversized receipts and missing or
weak (<32-byte) keys. It then passes the authenticated record through the
existing strict approval/comment/run/artifact binding and returns only
BOUND_FOR_REVIEW_ONLY. The unit tests use synthetic secrets and never call
Claude, Notion, or GitHub writes.

The HMAC proves only knowledge of the verifier key, **not** that the genuine
protected Notion gate approved the task: production requires an isolated trusted
signer, key provenance/rotation controls, authenticated workflow identity,
durable anti-replay, and independent re-check of private Notion approval.
Never put the HMAC key in the repository, task fields, GitHub issue comments,
generated artifacts, browser, or customer-facing logs. Do not allow arbitrary
callers to submit their own key or signed receipt and call it authorization.
Do not enable the paid implementation or publish job from this module alone.

The ChatGPT Notion connector's current account-link error is separate from
the repository code: restoring its eligible personal account link requires
external OAuth/account authorization, and a successful GitHub CI run does
not repair or bypass that identity failure.


## Local replay protection: one artifact per task revision (2026-11-23)

The SQLite `ReplayLedger` now enforces uniqueness on `(repo, task_digest)`,
not only on `(repo, run_id, artifact_id)`. A second run or artifact for
the same approved task digest is blocked even if both provider IDs differ.
A genuine changed task scope has a different digest and can be reserved
independently, subject to fresh upstream approval.

Existing local SQLite ledgers are migrated using a unique index; historical
duplicate task reservations cause a fail-closed
`ambiguous_existing_task_reservations` error, **not** automatic deletion,
replacement or arbitrary selection of a winner. Do not silently discard
historical reservations; reconcile them with audit evidence manually.

This remains an OFFLINE, local-disk replay guard. It is not a cloud-distributed
or cross-runner atomic lock; production activation needs a durable, shared
transactional store with protected credentials and recovery semantics.


## Atomic local ledger initialization hardening (2026-11-23)

SQLite schema setup and the per-task uniqueness index are now created in
one `BEGIN IMMEDIATE` transaction. This avoids the initialization window
between creating a legacy-compatible table and adding the unique index, and
rolls back the migration when existing task-digest duplicates are detected.
A symbolic-link database file path is refused. These checks protect the
local review-only ledger and do not establish security of parent directories
or make the storage durable across different GitHub hosted runners.

Tests cover parallel attempts with distinct run/artifact IDs for the same
task digest, preservation of duplicate historical rows after a rejected
migration, and refusal of a symlink database path.

Production deployment still requires an independently managed shared durable
lock store, authenticated protected-gate data, operational recovery and a
readiness review. Do not enable privileged publishing solely because the
local SQLite tests pass.


## Cross-runner PostgreSQL reservation adapter (2026-11-23)

The draft-only `tools/handoff/postgres_replay_ledger.py` implements a shared
PostgreSQL reservation store as an alternative to the local SQLite ledger.
The table has independent uniqueness constraints on `(repo, task_digest)` and
`(repo, run_id, artifact_id)`. A transaction inserts with
`ON CONFLICT DO NOTHING RETURNING state`; an already used task/run cannot
be reserved twice, even by distinct runners. The consuming transition is
conditional on exact digest/run/artifact/patch and `RESERVED` state.
Ambiguous network outcomes must be reconciled against the database; the
adapter intentionally does not auto-release or blindly retry reservations.

CI now runs an **isolated disposable PostgreSQL 16 service** and psycopg client
via the `postgres-integration` job. Five live integration tests cover
reservation persistence, consumption, refusal to reuse a task with another
artifact, refusal of wrong-patch consumption, and 12 concurrent connections
competing for one task digest (exactly one commit). The normal offline test
suite additionally exercises parameter validation and SQL contract using a
SQLite test double. The local test-double suite is not itself PostgreSQL proof.

Production limitations: the test database credentials embedded in CI are
synthetic and scoped ONLY to a disposable CI service. A real deployment must
use its own isolated PostgreSQL instance, least-privilege runtime role,
separate schema migration role, encrypted connections, backups, access audits,
durable recovery/reconciliation, and proof of authentication of the protected
approval record. The new adapter is **not** wired to the paid Claude workflow,
Draft PR publisher, or external production environment, and never authorizes
a merge/deployment. The broken ChatGPT Notion account link remains independent.
