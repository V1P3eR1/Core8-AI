# Core8 engineering continuity when Notion is unavailable

## Problem / solution

The ChatGPT Notion connector can return `link_id must identify an eligible linked account` before a page can be queried. Repeated connection attempts should not block *read-only engineering visibility* into GitHub.

This **GitHub-only continuity mode** does not replace the private LEV OS or the approved Notion task queue. It is a deliberately limited read-only status report for existing review PRs, built from GitHub REST pull request metadata and check-run conclusions. It never includes PR titles, issue descriptions, user/private task content, API key values or Notion data.

### Usage

```bash
python tools/handoff/github_continuity.py --format markdown
python tools/handoff/github_continuity.py --format json
python -m unittest discover -s tools/handoff -p 'test_*.py' -v
```

`GITHUB_TOKEN` may be passed through the environment for authenticated **GET-only** calls. A public repository can be queried without a token, subject to low API rate limits. Requests refuse HTTP redirects. Unexpected response formats, incomplete check-run inventories, ambiguous duplicate check names, missing check runs and foreign PR heads fail closed or are marked not green.

The review-only workflow `.github/workflows/github-continuity.yml` is scheduled daily and can also be triggered manually **only after** it is separately reviewed and merged. Until then it is a draft. It uses read-only `contents`, `pull-requests`, `checks` permissions and writes a GitHub Actions run summary, not any repository contents, issues, Notion pages, approvals or customer records. Existing independent hourly monitoring is unaffected.

### Exact limitations

- **All Notion approvals are NOT VERIFIED** in degraded mode.
- A green check run is **not** human approval, source provenance, a production-readiness determination or permission to spend money.
- No Claude API execution, GitHub branch/PR publication, merge, deployment or client communication is started here.
- Check-run summaries can have stale/incomplete data: a GitHub API response with partial pagination is blocked rather than falsely marked green.
- The task queue stays in protected Notion. Restore eligible Notion connector identity and exact page/data-source sharing; never copy sensitive knowledge into GitHub to compensate for an outage.
- Before enabling a real zero-copy writer: review the existing #65→#67→#74, #68→#71→#75→#76, #72→#73→#78 and #77→#79 draft chains, then independently check live owner authorization, durable replay claims and no-secret execution boundaries.

This is a **continuity and observability fallback**, not a parallel authorization workflow.
