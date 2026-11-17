---
name: core8-build
description: "Plan, implement, verify, and review Core8-AI code. Use for scoped changes, repository mapping, PR preparation, functional browser tests, and release checks."
---

# Build & Test

Read `docs/core8-agents/README.md` and the `Build & Test` section of `docs/core8-agents/catalog.md` for capabilities 01–08. Apply the steps relevant to the requested capability and return the handoff.

1. Read the repository instructions and working tree. Find the existing entry point, workflow, and tests before choosing a change.
2. Record acceptance criteria, write the smallest change that meets them, and run the applicable lint, tests, and build from the normal project entry points.
3. Use Playwright for ordinary user flows on an authorized local or staging app. Save failure details or screenshots when they add evidence.
4. For capability 07, use an independent Codex session to review the same base and head or exact local diff. Keep the reviewer out of the implementation and send the findings back with file references.
