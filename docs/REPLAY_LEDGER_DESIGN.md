# Replay ledger — local design experiment

This is a **SQLite reservation primitive**, not an activated Claude or GitHub workflow. It prevents a second writer from claiming an identical `(repo, run_id, artifact_id)` in the **same shared durable database**. It also rejects reusing that identity with different hashes.

- The caller must validate independent GitHub provenance and task approval *before* reserving.
- A reserved artifact is **never silently retried**. A crash leaves it RESERVED until a human investigates. No automatic deletion or reset of reservations is provided.
- This does not solve distributed locking if every job has its own ephemeral disk. The future production design requires a durable secured shared transactional store with backup, authorization, recovery procedure and concurrency tests.
- Do not put database files, credentials, artifact contents or personal data into public GitHub.
- Never perform `mark_consumed` before the intended draft-PR write is confirmed; failures after a remote write require reconciliation, not blind retry.
- There is no active automation, cost, deployment or PR publishing in this change.

Run on branch: `python -m unittest discover -s tools/handoff -p 'test_*.py' -v`

Track: Issue #62, draft PR #68, draft PR #65. Proposed follow-up: independent trusted GitHub fetcher and no-secret isolated patch application, then narrowly scoped draft PR writer.
