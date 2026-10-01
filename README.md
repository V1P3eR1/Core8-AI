# Core8-AI

Canonical repository for Core8-AI — AI agents that run business operations.

| Path | What |
|---|---|
| `apps/core8-platform/` | Multi-agent business automation platform (FastAPI + Next.js): CRM leads, calendar, design, Instagram growth & publishing |
| `apps/my-goddess-orchestra/` | Voice "CEO" orchestrator over 274 specialist personas (local, HE/EN) |
| `tools/setup/` | Windows / Claude Desktop bootstrap |
| `docs/` | Inventory, agents catalog, architecture, integrations, tech debt, deployment |

Start with [`docs/CORE8_INVENTORY.md`](docs/CORE8_INVENTORY.md).

## Rules

- **Never commit secrets or customer data.** Only `*.example` env templates. CI (`secret-scan`) blocks leaks on every PR.
- **No direct pushes to `main`.** All changes go through a branch + Pull Request.

## How Claude Code and ChatGPT collaborate

GitHub is the communication layer between the two agents — Lev should not have to relay reports.

- **Issues** = work items and questions. Label with the owner: `claude-code`, `chatgpt`, or `needs-lev` (a decision only Lev can make).
- **Pull Requests** = proposed changes. The author agent opens it; the other agent reviews via PR comments.
- Reports, audits and findings go into the PR description or an Issue comment, not into chat.
- Only `needs-lev` items require Lev's attention. Lev merges.
