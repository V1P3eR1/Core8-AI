"""Read-only, single-PR CI preview with exact current-head verification.

Only gathers a public-repository PR and current SHA check-run metadata. No
private Notion token, customer content, write API, model invocation or deploy.
Never trust pull request text as commands. Preview may observe its own running
check and must not represent an approval to merge.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError

from dev_loop_health import get_json, report, REPO, SHA, MAX_CHECKS


class PreviewError(ValueError):
    pass


def snapshot(number, expected_head, fetch=get_json, token=""):
    if type(number) is not int or number < 1 or number > 1_000_000:
        raise PreviewError("invalid_pr")
    if not isinstance(expected_head, str) or not SHA.fullmatch(expected_head):
        raise PreviewError("invalid_expected_head")
    pr = fetch(f"/pulls/{number}", token)
    if not isinstance(pr, dict) or pr.get("number") != number:
        raise PreviewError("unexpected_pr_response")
    if pr.get("state") != "open":
        raise PreviewError("pr_not_open")
    head = (pr.get("head") or {}).get("sha")
    if head != expected_head:
        raise PreviewError("stale_pr_head")
    repo = (pr.get("head") or {}).get("repo") or {}
    if repo.get("full_name") != REPO:
        raise PreviewError("external_pr_head")
    checks = fetch(f"/commits/{expected_head}/check-runs?per_page=100", token)
    if not isinstance(checks, dict) or not isinstance(checks.get("check_runs"), list):
        raise PreviewError("invalid_check_response")
    rows = checks["check_runs"]
    if len(rows) > MAX_CHECKS:
        raise PreviewError("truncated_check_evidence")
    output = report([pr], {expected_head: rows}, datetime.now(timezone.utc).isoformat())
    output["source"] = "github_current_head_pr"
    output["snapshot_only"] = True
    output["self_check_may_be_pending"] = True
    output["approval"] = "not_granted"
    return output


def main():
    try:
        number = int(os.environ.get("CORE8_PREVIEW_PR", ""))
        sha = os.environ.get("CORE8_PREVIEW_HEAD_SHA", "")
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            raise PreviewError("missing_readonly_token")
        result = snapshot(number, sha, token=token)
        with open("core8-dev-loop-report.json", "w", encoding="utf-8") as fp:
            json.dump(result, fp, ensure_ascii=False, sort_keys=True, indent=2)
        print(json.dumps({"source": "github_current_head_pr", "pr": number,
                          "mode": "observe_only", "approval": "not_granted"}))
    except (HTTPError, URLError, TimeoutError, PreviewError, ValueError, KeyError, TypeError):
        print("pr_preview_snapshot_failed", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
