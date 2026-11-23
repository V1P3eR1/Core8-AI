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
