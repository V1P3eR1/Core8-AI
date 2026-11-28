"""A bounded read-only repo-wide GitHub PR snapshot for draft branch demos.

Only GitHub metadata. Never imports private Notion, issues, issue bodies, model
prompts or customer content. Designed for same-repository trusted CI only.
Snapshot is intentionally capped to avoid uncontrolled hourly API fan-out.
"""
import json
import os
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from dev_loop_health import get_json, report, SHA, MAX_CHECKS

MAX_PREVIEW_PRS = 20
MAX_LIST_PAGE = 100

class RepoPreviewError(ValueError):
    pass

def capture(fetch=get_json, token=""):
    response = fetch("/pulls?state=open&per_page=100", token)
    if not isinstance(response, list):
        raise RepoPreviewError("invalid_pr_listing")
    if len(response) == MAX_LIST_PAGE:
        # Cannot prove completeness without a second page. Report partial.
        list_complete = False
    else:
        list_complete = True
    if len(response) > MAX_PREVIEW_PRS:
        # Explicitly report coverage limit, rather than claiming "all PRs."
        selected = response[:MAX_PREVIEW_PRS]
        coverage = "partial"
    else:
        selected = response
        coverage = "complete" if list_complete else "partial"
    numbers = set()
    checks = {}
    clean_prs = []
    for pr in selected:
        if not isinstance(pr, dict):
            raise RepoPreviewError("invalid_pr_data")
        number = pr.get("number")
        head = (pr.get("head") or {}).get("sha", "")
        if type(number) is not int or number < 1 or number > 1000000 or number in numbers:
            raise RepoPreviewError("duplicate_or_invalid_pr")
        if not isinstance(head, str) or not SHA.fullmatch(head):
            raise RepoPreviewError("missing_current_sha")
        if pr.get("state") != "open":
            raise RepoPreviewError("not_open")
        numbers.add(number)
        check_response = fetch(f"/commits/{head}/check-runs?per_page=100", token)
        if not isinstance(check_response, dict) or not isinstance(check_response.get("check_runs"), list):
            raise RepoPreviewError("invalid_checks")
        check_rows = check_response["check_runs"]
        if len(check_rows) >= MAX_CHECKS:
            # A full first page cannot prove it includes all checks.
            # Refuse to report it as if successful checks were exhaustive.
            raise RepoPreviewError("check_page_not_exhaustive")
        checks[head] = check_rows
        clean_prs.append(pr)
    out = report(clean_prs, checks, datetime.now(timezone.utc).isoformat())
    out["source"] = "github_repo_open_prs"
    out["snapshot_only"] = True
    out["coverage"] = coverage
    out["selected_pr_count"] = len(selected)
    out["max_preview_prs"] = MAX_PREVIEW_PRS
    out["total_open_prs_lower_bound"] = len(response)
    out["approval"] = "not_granted"
    return out

def main():
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise SystemExit("missing_readonly_token")
    try:
        result = capture(token=token)
        with open("core8-dev-loop-report.json", "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
        print(json.dumps({"source": result["source"], "coverage": result["coverage"],
                          "inspected": result["scanned_prs"], "approval": "not_granted"}))
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, TypeError):
        print("repo_preview_snapshot_failed", file=sys.stderr)
        raise SystemExit(1) from None

if __name__ == "__main__":
    main()
