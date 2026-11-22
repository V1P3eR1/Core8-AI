"""GitHub-only, read-only Core8 orchestration continuity report.

Degraded mode while Notion connector is inaccessible. Reports observable GitHub
facts only. NEVER synthesizes a Notion approval or authorizes a Claude execution.
No writable GitHub endpoints, secrets, private task bodies, or local state.
"""
import argparse
from datetime import datetime, timezone
import json
import re
import sys
from urllib import error, request

REPO = "V1P3eR1/Core8-AI"
BASE = "https://api.github.com/repos/" + REPO
MAX_REPLY = 250_000
CHAINS = {
    "patch_stage_draft": (65, 67, 74),
    "artifact_provenance": (68, 71, 75, 76),
    "offline_review": (72, 73, 78),
    "callback": (77, 79),
    "release_safety": (55, 70),
}
CHECKS = frozenset({"success", "failure", "cancelled", "timed_out", "neutral", "skipped", "action_required", "stale"})


class SnapshotBlocked(ValueError):
    pass


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def get_json(endpoint, token=None):
    if not re.fullmatch(r"/(?:pulls/[1-9][0-9]*|commits/[a-f0-9]{40}/check-runs)", endpoint):
        raise SnapshotBlocked("invalid_endpoint")
    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "core8-continuity-read-only"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = request.Request(BASE + endpoint, headers=headers, method="GET")
    try:
        with request.build_opener(NoRedirect).open(req, timeout=12) as response:
            if response.geturl() != BASE + endpoint:
                raise SnapshotBlocked("redirect_blocked")
            data = response.read(MAX_REPLY + 1)
    except (error.HTTPError, error.URLError, OSError, TimeoutError) as exc:
        raise SnapshotBlocked("github_read_unavailable") from None
    if len(data) > MAX_REPLY:
        raise SnapshotBlocked("response_too_large")
    try:
        result = json.loads(data)
    except (ValueError, UnicodeError):
        raise SnapshotBlocked("malformed_response") from None
    if not isinstance(result, dict):
        raise SnapshotBlocked("malformed_response")
    return result


def summarize_pr(pr, checks, number):
    """Redacted, bounded, fail-closed metadata. No body, title or task scope."""
    if type(pr.get("number")) is not int or pr["number"] != number:
        raise SnapshotBlocked("pr_identity_mismatch")
    head = pr.get("head") or {}
    base = pr.get("base") or {}
    repo = (head.get("repo") or {}).get("full_name")
    if repo != REPO:
        raise SnapshotBlocked("unexpected_head_repository")
    sha = head.get("sha")
    if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise SnapshotBlocked("invalid_pr_head")
    if not isinstance(checks, dict) or not isinstance(checks.get("check_runs"), list):
        raise SnapshotBlocked("checks_missing")
    total = checks.get("total_count")
    if type(total) is not int or total != len(checks["check_runs"]):
        # The GitHub check-runs endpoint paginates by default. A partial page
        # must NEVER be classified as all green.
        raise SnapshotBlocked("incomplete_check_inventory")
    records = {}
    for c in checks["check_runs"]:
        if not isinstance(c, dict) or not isinstance(c.get("name"), str):
            raise SnapshotBlocked("invalid_check")
        name = c["name"]
        if name in records:  # Duplicate latest-name ambiguity must not falsely turn green.
            raise SnapshotBlocked("duplicate_check_names")
        conclusion = c.get("conclusion")
        status = c.get("status")
        if status != "completed":
            records[name] = "pending"
        elif conclusion in CHECKS:
            records[name] = conclusion
        else:
            records[name] = "unknown"
    # A single unrelated green check must not masquerade as the required
    # review gates. Each tracked PR needs its expected test suite AND secret scan.
    suite = ("release preflight (offline)" if number in (55, 70) else
             "Orchestration staging offline unit tests" if number in (67, 74) else
             "Handoff contract tests")
    required = {"secret-scan", suite}
    if not records:
        check_state = "no_checks"
    elif not required.issubset(records):
        check_state = "missing_required_checks"
    elif any(records[k] == "pending" for k in required):
        check_state = "pending"
    elif any(records[k] != "success" for k in required):
        check_state = "needs_review"
    elif any(value != "success" for value in records.values()):
        check_state = "needs_review"
    else:
        check_state = "passed"
    state = pr.get("state")
    if state not in ("open", "closed"):
        raise SnapshotBlocked("unknown_pr_state")
    merged = pr.get("merged_at") is not None
    if merged and state != "closed":
        raise SnapshotBlocked("inconsistent_merge_state")
    return {
        "number": number, "url": f"https://github.com/{REPO}/pull/{number}",
        "head_sha": sha, "base_ref": base.get("ref") if isinstance(base.get("ref"), str) else None,
        "state": "merged" if merged else state,
        "draft": pr.get("draft") is True,
        "check_state": check_state,
        "checks": dict(sorted(records.items())),
    }


def make_snapshot(fetch, *, checked_at):
    if not isinstance(checked_at, str):
        raise SnapshotBlocked("invalid_checked_at")
    grouped = {}
    for name, numbers in CHAINS.items():
        group = []
        for number in numbers:
            pr = fetch(f"/pulls/{number}")
            sha = (pr.get("head") or {}).get("sha")
            if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha):
                raise SnapshotBlocked("invalid_pr_head")
            checks = fetch(f"/commits/{sha}/check-runs")
            group.append(summarize_pr(pr, checks, number))
        grouped[name] = group
    return {
        "schema": 1, "repository": REPO, "checked_at": checked_at,
        "notion_state": "NOT_VERIFIED",
        "execution_authorized": False,
        "claude_paid_execution_enabled_by_report": False,
        "github_write_performed": False,
        "chains": grouped,
        "limitations": "Checks are historical observations, not approval, CI policy or deployment readiness.",
    }


def render_markdown(snapshot):
    lines = [
        "# Core8 — GitHub-only continuity snapshot", "",
        f"Checked (UTC): {snapshot['checked_at']}", "",
        "**Notion approval: NOT VERIFIED. Paid Claude / merges / deployments: NOT AUTHORIZED by this report.**",
        "", "| Chain | PR | State | Checks |", "|---|---|---|---|",
    ]
    for chain, items in snapshot["chains"].items():
        for item in items:
            state = item["state"] + (" (draft)" if item["draft"] and item["state"] == "open" else "")
            lines.append(f"| {chain} | [#{item['number']}]({item['url']}) | {state} | {item['check_state']} |")
    lines += ["", "This is a read-only engineering dashboard. Do not infer current Notion approval from GitHub checks."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args(argv)
    from os import environ
    try:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        snapshot = make_snapshot(
            lambda p: get_json(p, environ.get("GITHUB_TOKEN")), checked_at=now)
    except SnapshotBlocked as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(snapshot, sort_keys=True, indent=2))
    else:
        print(render_markdown(snapshot), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
