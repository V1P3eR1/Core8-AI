"""Core8-AI cloud control plane: read-only deterministic CI triage.

This module does not run an LLM, execute generated code, write GitHub issues,
merge, deploy, schedule paid API calls, or access customer data. It produces a
bounded redacted artifact for the already-approved engineering lane.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

REPO = "V1P3eR1/Core8-AI"
BASE = "https://api.github.com/repos/" + REPO
BAD = {"failure", "timed_out", "action_required"}
INCOMPLETE = {"cancelled", "skipped", "stale", "startup_failure"}
ACCEPTED = {"success", "neutral"}
PENDING = {"queued", "in_progress", "requested", "waiting", "pending"}
SHA = re.compile(r"^[a-f0-9]{40}$")
MAX_PRS = 60
MAX_CHECKS = 100


def get_json(path, token):
    if not path.startswith("/") or "://" in path or ".." in path:
        raise ValueError("invalid API path")
    req = Request(BASE + path, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "core8-orchestration-watch",
    })
    with urlopen(req, timeout=20) as res:
        return json.load(res)


def classify(prs, checks_by_sha):
    """No PR bodies, comments, secrets, arbitrary instructions or model prompts."""
    outcomes = []
    for pr in prs[:MAX_PRS]:
        num, head = pr.get("number"), (pr.get("head") or {}).get("sha", "")
        if not isinstance(num, int) or not SHA.fullmatch(head):
            continue
        checks = checks_by_sha.get(head, [])[:MAX_CHECKS]
        # A failed historical workflow must never override a newer successful
        # result for the *same named check* on the same head SHA.
        latest = {}
        for c in checks:
            name = c.get("name", "")
            if not isinstance(name, str) or not name or len(name) > 160:
                continue
            item = latest.get(name)
            if item is None or (str(c.get("started_at") or ""), int(c.get("id") or 0)) > (
                str(item.get("started_at") or ""), int(item.get("id") or 0)
            ):
                latest[name] = c
        failing = sorted(n for n, c in latest.items() if c.get("conclusion") in BAD)
        pending = sorted(n for n, c in latest.items() if c.get("status") in PENDING)
        inconclusive = sorted(n for n, c in latest.items() if c.get("conclusion") in INCOMPLETE or
                              (c.get("status") == "completed" and c.get("conclusion") not in BAD | INCOMPLETE | ACCEPTED))
        labels = {x.get("name") for x in pr.get("labels", []) if isinstance(x, dict)}
        # Never auto-run a code writer just because a PR has a failure.
        state = ("needs_human_triage" if failing else "checks_pending" if pending
                 else "incomplete_check_evidence" if inconclusive
                 else "review_gate" if latest else "missing_check_evidence")
        outcomes.append({
            "pr": num, "head_sha": head, "draft": bool(pr.get("draft")),
            "state": state, "failed_checks": failing[:12],
            "pending_count": len(pending), "inconclusive_checks": inconclusive[:12],
            "check_count": len(latest),
            "approval": "not_granted_by_this_report",
            "priority": "p0" if "core8:priority:p0" in labels else "normal",
        })
    outcomes.sort(key=lambda x: (
        0 if x["state"] == "needs_human_triage" else 1,
        0 if x["priority"] == "p0" else 1, x["pr"]))
    return outcomes


def report(prs, checks, timestamp):
    rows = classify(prs, checks)
    return {
        "schema": "core8-dev-loop-health-v1",
        "generated_at": timestamp,
        "repository": REPO,
        "mode": "observe_only",
        "scanned_prs": len(rows),
        "next_action": ({
            "type": "review_ci_failure", "pr": rows[0]["pr"],
            "sha": rows[0]["head_sha"], "reason": "failed_check_on_current_head"
        } if rows and rows[0]["state"] == "needs_human_triage" else {
            "type": "await_review_or_approved_work", "reason": "no_current_ci_failures"
        }),
        "items": rows,
        "boundaries": {
            "may_commit": False, "may_merge": False, "may_deploy": False,
            "may_spend": False, "may_message_customers": False,
            "requires_existing_scope_approval_for_implementation": True
        },
    }


def main():
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise SystemExit("missing_readonly_github_token")
    try:
        prs = get_json("/pulls?state=open&per_page=100", token)[:MAX_PRS]
        checks = {}
        for pr in prs:
            sha = (pr.get("head") or {}).get("sha", "")
            if SHA.fullmatch(sha):
                result = get_json("/commits/" + sha + "/check-runs?per_page=100", token)
                checks[sha] = result.get("check_runs", [])[:MAX_CHECKS]
        output = report(prs, checks, datetime.now(timezone.utc).isoformat())
        with open("core8-dev-loop-report.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, sort_keys=True)
        print(json.dumps({
            "mode": "observe_only", "scanned_prs": output["scanned_prs"],
            "next_action": output["next_action"], "report": "core8-dev-loop-report.json"
        }))
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as exc:
        # Do not print response body/headers/token if a provider is failing.
        print("control_plane_snapshot_failed", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
