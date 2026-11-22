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
