# Cloud AI collaboration setup — phone + laptops + desktop

## Status
This PR *proposes* the workflow, not an already active Claude session. Activation requires merging this PR and configuring credentials and the GitHub app. No PC needs to be online after cloud activation.

## Owner setup (one-time)
1. Review and merge this PR after checking permissions and cost implications.
2. Install the official Claude GitHub App on **only** V1P3eR1/Core8-AI: https://github.com/apps/claude
3. Add repository Actions secret `ANTHROPIC_API_KEY` via GitHub Settings → Secrets and variables → Actions. Use a separate restricted API key with a spend limit, not a personal credential pasted into issues.
   - Alternative OAuth token authentication is possible, but requires changing the workflow secret/input; do not add both.
4. Check GitHub Settings → Actions: allow required actions, ensure permissions and repository policies allow the workflow.
5. Test on an innocuous sample issue (documentation typo). An authorized collaborator comments `@claude please propose a docs-only fix` or labels the issue `claude-ready` (create this label if it does not exist).
6. Verify an Actions run appears and Claude returns an issue comment and/or branch. Review generated changes and a PR before merging.
7. Confirm cost tracking and alerts in Anthropic and GitHub. Use the provider budget as the spending control; timeout and --max-turns are only secondary caps.

## Daily use from any device
- Phone: create an issue with outcome and acceptance criteria; add `claude-ready` once vetted; follow results in GitHub mobile.
- Laptop/Desktop: same GitHub issues, PRs and branch; optionally run local Claude Code with the cloned repo.
- ChatGPT: discuss strategy or request scoped GitHub issues. ChatGPT cannot automatically read every conversation into Claude; include approved instructions in the issue/CLAUDE.md. Private family/finance details stay out of this public repository.
- Changes run in GitHub-hosted infrastructure, not on Lev's computers.
- Before merging: CI green, secrets scan clean, tests pass, no production impact, approved by Lev.

## Not automated by this PR
- ChatGPT messages automatically triggering an issue or tagging it without explicit tool activity.
- Claude automatically taking every new issue without a readiness label or authorized mention.
- Bidirectional Notion/Obsidian sync.
- Production deployment, DNS, billing, key rotation, customer messaging or social-media publication.
- Automatic ChatGPT code review after every PR (requires a separate event-driven integration).

## Operational risks
- Repository is public: issue and PR content are public. Never add private data.
- Tokens cannot be copied across providers; use repository Secrets only.
- API calls and GitHub Actions may incur costs.
- Agent output, build results, permissions and downstream workflows must be validated before claims of success.
- If the workflow fails, inspect the Actions run; do not assume execution completed.

Official docs: https://github.com/anthropics/claude-code-action/blob/main/docs/setup.md
