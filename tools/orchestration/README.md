# Core8 Patch Preflight — V1

This is a **local deterministic preflight** for proposed Claude Code patch artifacts. It is **not** an executor, PR publisher, trusted parser, security sandbox, secret scanner, approval authority or production service.

## Run

```bash
python -m unittest discover -s tools/orchestration -p 'test_*.py' -v
```

Local prototype execution on 2026-11-22: **13/13 tests passed** in isolated Python. CI, live Claude patch artifacts and repository-wide integration have NOT been tested.

## Validates

- Strict git diff header with same source/target path (renames/copies forbidden).
- Files only in `apps/` or `docs/`; rejects traversal, hidden control folders, env files, private keys, binary/SQL/database archives.
- Rejects symlink/submodule/executable mode changes, binary patches, duplicates, >20 files or >300 KB patch.

## Additional mandatory gates BEFORE any automatic PR

- A full real patch parser and `git apply --check` in disposable checkout; reject unrecognized headers, malformed hunks, unexpected worktree changes and symlinks.
- Authoritative GitHub run and immutable artifact-id provenance, SHA256, exact approved task digest, replay/idempotency and expiry.
- No secrets or network in untrusted check job; do not execute generated code with production privileges.
- Narrow bot credentials only in isolated publishing job; draft PR only with human approval for merges.
- Document test evidence, fail-closed outcome, and cancellation/cost bounds.

Tracking: Issue #62 and proposal PR #61. This branch does not modify existing production code or actions.
