"""Render a bounded read-only Core8 engineering health dashboard.

Input is the already minimized output of the GitHub observer, with an optional
local read-only Notion reconciliation result. Nothing fetches or sends data.
Untrusted GitHub check names must never become Markdown/HTML instructions.
"""
import json
import re
import sys
from pathlib import Path

REPO = "V1P3eR1/Core8-AI"
SHA = re.compile(r"^[a-f0-9]{40}$")
SCHEMA = "core8-dev-loop-health-v1"
VALID_STATES = {
    "needs_human_triage": "Failure needs triage",
    "checks_pending": "Checks still running",
    "incomplete_check_evidence": "Incomplete CI evidence",
    "review_gate": "Review required",
    "missing_check_evidence": "No check evidence",
}
MAX_ITEMS = 60
MAX_SIZE = 250_000


class DashboardError(ValueError):
    pass


def _text(value, limit=100):
    if not isinstance(value, str):
        return "unknown"
    # Never render untrusted raw Markdown, URLs, HTML, control characters,
    # bidirectional overrides or newlines in a table cell.
    safe = "".join(x if x.isascii() and (x.isalnum() or x in "._ -") else "_"
                   for x in value if x.isprintable() and ord(x) < 127)
    return (safe[:limit].strip() or "unknown")


def render(health, notion=None):
    if not isinstance(health, dict) or health.get("schema") != SCHEMA:
        raise DashboardError("invalid_health_schema")
    if health.get("mode") != "observe_only":
        raise DashboardError("not_readonly")
    items = health.get("items")
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise DashboardError("invalid_health_items")
    demo = health.get("demo") is True
    counts = {k: 0 for k in VALID_STATES}
    rows = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise DashboardError("invalid_health_item")
        n, sha, status = item.get("pr"), item.get("head_sha"), item.get("state")
        if type(n) is not int or not 1 <= n <= 1_000_000 or n in seen:
            raise DashboardError("invalid_or_duplicate_pr")
        if not isinstance(sha, str) or not SHA.fullmatch(sha) or status not in counts:
            raise DashboardError("invalid_head_or_state")
        seen.add(n)
        counts[status] += 1
        checks = item.get("failed_checks", [])
        if not isinstance(checks, list):
            raise DashboardError("invalid_check_list")
        visible = ", ".join(_text(x, 60) for x in checks[:3])
        pr_label = f"Demo #{n}" if demo else f"[#{n}](https://github.com/{REPO}/pull/{n})"
        rows.append(
            f"| {pr_label} | "
            f"{VALID_STATES[status]} | \`{sha[:10]}\` | "
            f"{visible or '-'} |"
        )
    lines = [
        "# Core8-AI engineering control — observation only",
        *(["", "**SYNTHETIC DEMO DATA — NOT LIVE GITHUB CHECKS.**"] if demo else []),
        "",
        f"**GitHub PRs checked:** {len(items)}. This report does not approve code, "
        "authorize model spending, merge or deploy anything.",
        "",
        "## Current check states",
        "",
        *[f"- {VALID_STATES[key]}: {count}" for key, count in counts.items()],
        "",
        "## PR evidence",
        "",
        "| Pull request | State | Current SHA | Failed checks (max 3) |",
        "| --- | --- | --- | --- |",
        *(rows or ["| - | No tracked pull requests | - | - |"]),
        "",
    ]
    if notion is None:
        lines += [
            "## Private Notion synchronization",
            "",
            "Not checked by this GitHub Actions report. No private Notion connection "
            "or export was used. Do not infer task approvals from GitHub metadata.",
            "",
        ]
    else:
        if not isinstance(notion, dict) or notion.get("schema") != "core8-notion-github-readonly-audit-v1":
            raise DashboardError("invalid_notion_schema")
        if notion.get("mode") != "observe_only" or notion.get("can_change_notion") is not False:
            raise DashboardError("unsafe_notion_report")
        # Only counts are displayed. Do not print task IDs, scope, notes,
        # approval evidence or private Notion URLs.
        nt, linked, attention = (notion.get(x) for x in
                                 ("task_count", "linked_task_count", "attention_count"))
        if any(type(x) is not int or x < 0 or x > 100 for x in (nt, linked, attention)):
            raise DashboardError("invalid_notion_counts")
        if linked > nt or attention > nt:
            raise DashboardError("inconsistent_notion_counts")
        lines += [
            "## Private Notion synchronization (user-supplied audited snapshot)",
            "",
            f"- Tasks inspected: {nt}",
            f"- Linked GitHub issues: {linked}",
            f"- Tasks with diagnostic flags: {attention}",
            "- No private task content, approval evidence or direct identifiers are included.",
            "- Snapshot alone cannot authorize execution.",
            "",
        ]
    lines += [
        "## Next step",
        "",
        ("Investigate the failing checks on the **current PR head SHA**; "
         "use existing human approval gates before any repair."
         if counts["needs_human_triage"] else
         "Review pending/blocked evidence or choose a separately authorized task. "
         "A passing check is not merge permission."),
        "",
        "**Boundaries:** read-only · synthetic/metadata evidence only · "
        "no production changes · no autonomous model calls.",
        "",
    ]
    return "\n".join(lines)


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: dashboard_report.py health.json [notion-audit.json]")
    try:
        def load(path):
            p = Path(path)
            if not p.is_file() or p.stat().st_size > MAX_SIZE:
                raise DashboardError("invalid_input_file")
            return json.loads(p.read_text(encoding="utf-8"))
        output = render(load(sys.argv[1]), load(sys.argv[2]) if len(sys.argv) == 3 else None)
        Path("core8-dev-loop-report.md").write_text(output, encoding="utf-8")
        print("core8_dashboard_rendered read_only=true")
    except (OSError, UnicodeError, ValueError):
        print("core8_dashboard_rejected", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
