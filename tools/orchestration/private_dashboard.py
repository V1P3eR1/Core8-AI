"""Private, local-only Core8 dashboard from *already verified* summary inputs.

This is intentionally not a GitHub Actions job or a hosted web endpoint.
Generate only within the user's private workspace, and never commit output.
No remote requests, API credentials, user/tenant identifiers or task descriptions.
"""
from html import escape
import json
from pathlib import Path
import sys

from dashboard_report import DashboardError, MAX_SIZE, SCHEMA, VALID_STATES
from private_task_summary import PrivateSummaryError

VALID_NOTION = frozenset({
    "Queued", "In progress", "Review", "Blocked", "Closed - unverified",
    "Awaiting approval",
})
MAX_OPEN = 1000


def _integer(value, max_value=MAX_OPEN):
    if type(value) is not int or not 0 <= value <= max_value:
        raise DashboardError("invalid_private_summary_count")
    return value


def private_html(notion, github):
    """Bounded server-rendered HTML; accepts aggregates, not task rows."""
    if not isinstance(notion, dict) or notion.get("schema") != "core8-private-metadata-summary-v1":
        raise DashboardError("untrusted_private_summary")
    if (notion.get("scope") != "private_local_only" or notion.get("mode") != "observe_only" or
        notion.get("may_publish_to_public_ci") is not False or
        notion.get("may_write_to_notion") is not False or
        notion.get("may_authorize_claude") is not False):
        raise DashboardError("unsafe_private_summary")
    if not isinstance(github, dict) or github.get("schema") != SCHEMA or github.get("mode") != "observe_only":
        raise DashboardError("invalid_github_summary")
    tasks, linked, attention = [_integer(notion.get(k), 100) for k in
                                ("tasks", "linked_issues", "needs_review")]
    if linked > tasks or attention > tasks:
        raise DashboardError("inconsistent_private_counts")
    statuses = notion.get("status_counts")
    if not isinstance(statuses, dict) or any(k not in VALID_NOTION for k in statuses):
        raise DashboardError("unsafe_status_name")
    if sum(_integer(n, 100) for n in statuses.values()) != tasks:
        raise DashboardError("inconsistent_status_counts")
    entries = github.get("items")
    if not isinstance(entries, list) or len(entries) > 60:
        raise DashboardError("unsafe_github_count")
    ci = {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("state") not in VALID_STATES:
            raise DashboardError("unknown_github_state")
        ci[entry["state"]] = ci.get(entry["state"], 0) + 1
    # No pass-through of arbitrary input strings, identifiers, links, timestamps,
    # source documents or secrets: only fixed labels + bounded integers.
    notion_rows = "".join(f"<tr><td>{escape(label)}</td><td>{statuses[label]}</td></tr>"
                          for label in sorted(statuses))
    ci_rows = "".join(f"<tr><td>{escape(VALID_STATES[label])}</td><td>{ci[label]}</td></tr>"
                      for label in sorted(ci))
    return f"""<!doctype html>
<html lang="he" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; img-src 'none'; form-action 'none'">
<title>Core8-AI — לוח פרטי</title><style>
body{{background:#0b1220;color:#f5f8ff;font:16px/1.65 system-ui,Arial,sans-serif;margin:0}}
main{{max-width:950px;padding:36px 18px;margin:auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}}
section{{border:1px solid #32405a;border-radius:14px;background:#18243a;padding:18px}}
table{{width:100%;border-collapse:collapse}}td{{padding:9px;border-bottom:1px solid #34435d}}
h1{{font-size:1.8rem}}strong{{font-size:2rem}}p,small{{color:#bdd0e9}}
</style></head><body><main>
<h1>Core8-AI · מרכז בקרה פרטי</h1>
<p>צילום מצב לקריאה בלבד: נתונים מצטברים בלבד, ללא פרטי לקוחות וללא סנכרון חי.</p>
<div class="grid">
<section><h2>Notion · תור עסקי</h2><strong>{tasks}</strong> משימות
<p>{linked} מקושרות ל־GitHub · {attention} דורשות בדיקה</p>
<table>{notion_rows}</table></section>
<section><h2>GitHub · בדיקות PR</h2><strong>{len(entries)}</strong> PRs שנבדקו
<table>{ci_rows}</table></section></div>
<p><small>הקובץ מיועד לסביבה פרטית בלבד. אין להעלות אותו ל־GitHub Actions ציבורי או להפעיל ממנו תהליכי אישור, מיזוג, הוצאה כספית או פריסה.</small></p>
</main></body></html>"""


def main():
    # Explicit private operator step only, not CI. Output path is chosen by the
    # private operator; the script never uploads or exposes these files.
    if len(sys.argv) != 4:
        raise SystemExit("usage: private_dashboard.py private-counts.json github-health.json output.html")
    if __import__("os").environ.get("GITHUB_ACTIONS") == "true":
        raise SystemExit("private_dashboard_forbidden_in_github_actions")
    def load(name):
        path = Path(name)
        if not path.is_file() or path.stat().st_size > MAX_SIZE:
            raise DashboardError("invalid_local_input")
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        out = private_html(load(sys.argv[1]), load(sys.argv[2]))
        path = Path(sys.argv[3])
        if path.suffix.lower() != ".html" or path.is_symlink():
            raise DashboardError("invalid_output_path")
        path.write_text(out, encoding="utf-8")
        print("private_dashboard_written_locally")
    except (OSError, UnicodeError, ValueError):
        print("private_dashboard_rejected", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
