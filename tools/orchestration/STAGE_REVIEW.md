# Zero-copy orchestration — isolated patch staging (stacked on PR #66)

Status: **DRAFT / REVIEW ONLY**. This is not the approved task gate, not Claude execution, not CI for generated code, and not a GitHub PR publisher.

The existing approval system remains in `tools/handoff/bridge.py` and `.github/workflows/claude-issues.yml`. Its human-authorized scope and artifact metadata must be verified **before** calling this script. Do not turn a GitHub comment, a synthetic manifest, or model text into an approval.

## What this slice adds

`stage_patch.py` consumes a trusted, pinned base commit and already-produced patch bytes. It verifies the artifact SHA-256, the source checkout's exact base SHA and clean state, and calls PR #66's pure `patch_gate.py`. It then exports the committed base into a disposable, local-only tree and performs `git apply --check` / `git apply` with no remote operations and no generated code execution. It checks the actual changed paths and file modes, produces a deterministic candidate hash and an idempotency key derived from `base + patch + approved scope`, then deletes the temporary tree.

CLI (from a clean checkout at the **already authenticated and approved** base SHA):

```sh
python3 tools/orchestration/stage_patch.py \
  --repo . \
  --patch /tmp/core8-implementation.patch \
  --artifact-sha256 SHA256_FROM_TRUSTED_RUN_METADATA \
  --base-sha APPROVED_FULL_COMMIT_SHA \
  --approved-scope-sha256 APPROVED_SCOPE_DIGEST
```

Tests: `python3 -m unittest discover -s tools/orchestration -p 'test_*.py' -v`. Offline, using generated disposable fixture repositories only.

## Explicit limits / next stages

- The digest only proves bytes match trusted metadata **if that metadata was obtained securely**. The runner must independently verify run identity, triggering human approval, scope revision, artifact expiry, repository identity and upstream permissions. This script does not.
- Staging in a temporary directory is **not a security sandbox**. Run in an unprivileged, no-secrets, no-network container/runner. No GITHUB_TOKEN write permission or provider API key may be present.
- A reviewer must validate patch parser edge cases, Unicode/file mode bypasses, resource limits and actual read-only runtime behavior before integration.
- The output is a **review manifest**. It cannot open a PR, merge, change production or charge AI usage. A future minimum-permission GitHub writer must verify this manifest against the upstream gate, deduplicate by idempotency key and create **Draft PR only**, separated from any job that processes an untrusted patch.
- Any status written back to Notion/GitHub needs its own scoped safe reporting job; a success here is not acceptance.
- Do not enable any paid Claude run, change deployment/DNS, or merge without Lev's separate explicit approval.
