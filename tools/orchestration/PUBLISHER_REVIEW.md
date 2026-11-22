# Zero-copy Stage 3 — Draft PR Publisher (review only)

Status: **draft, not activated**. Stacked on PR #67 (which is stacked on PR #66). No production workflow is enabled, no GitHub writer token configured, no merge/deploy or paid Claude run.

This implementation has two separate trust domains:

1. **Untrusted artifact processor — no secrets/no GitHub write access:** `stage_patch.py` verifies the artifact digest and exact approved-scope/base SHA supplied by the pre-existing human-authorized gate, applies the patch in a disposable local snapshot and checks observed paths/modes. Optional `--bundle-output /tmp/review-bundle.json` creates a new, immutable-by-convention package of regular-file additions/edits. Deleted files, symlinks and unsafe modes are rejected in bundle mode. The SHA-256 of the bundle is reported as evidence.
2. **Privileged writer — protected environment, no code execution:** `draft_publisher.py` re-verifies the bundle SHA-256, base/scope/artifact fields and each file's digest, allows only `apps/` and `docs/` paths, calculates a stable scope-bound branch name, and uses the GitHub Git Data REST API to create a **draft PR only**. It never checks out or executes generated source. If a matching draft PR exists it returns the existing URL; if a branch exists without a matching draft PR it fails closed for human reconciliation.

**Important:** The writer does **not** prove that the approved-scope file or bundle-digest came from the real human gate. Those values must be supplied by a trusted, separately authorized GitHub job after re-checking the canonical Notion/GitHub approval evidence, original run ID, repository identity, trigger identity, artifact provenance and current task version. Ordinary GitHub comments and AI-generated text do not authorize it.

Local test command:

```sh
python -m unittest discover -s tools/orchestration -p 'test_*.py' -v
```

Reviewable synthetic acceptance: tests create a disposable Git fixture, apply a mock patch, build a bundle, validate it, simulate GitHub API writes with a fake adapter, and assert Draft PR semantics and idempotency. No real token or network.

### Production activation gates — not satisfied
- Review and merge PR #66 and #67 independently; rebase this stacked draft after approval.
- Independent security review of all parsers, archive extraction, path/mode guards, size limits and remote write failure handling.
- Create a **separate, protected** read-only staging workflow and writer job. The staging job must have no secrets, no write token, no network if possible. The writer should receive a trusted bundle SHA and re-verify the existing human approval, scope digest and run identity; use minimum GitHub permissions.
- For GitHub Actions-created PRs, verify whether required CI triggers fire: the built-in GITHUB_TOKEN may not trigger further PR workflows. Use approved GitHub App credentials only after review if required, never a personal token in the patch job.
- Ensure staged bundle artifact provenance/retention, failure/retry reconciliation, report-back to GitHub/Notion, no self-approval, CI green, and human merge/deploy gates. The existing Notion connector is currently inaccessible from ChatGPT.
- Test a fully synthetic, zero-cost end-to-end in staging before any production or paid Claude run.

**Default CLI behavior:** `draft_publisher.py` is **dry-run** (validates and prints an idempotency key without network). `--apply` additionally requires `CORE8_PROTECTED_PUBLISH=1` and `GITHUB_TOKEN` from a protected job. These flags are accident prevention, not authentication. No automatic invocation has been added.

No step here authorizes financial charges, production deployments, DNS/credential changes, messaging customers, or publishing social content.
