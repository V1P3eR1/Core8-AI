"""Standalone offline HTML view of a sanitized Core8 CI snapshot.

Output is an *artifact*, not a hosted service. No scripts, third-party requests,
Notion credentials, content from issue bodies, or external asset dependencies.
"""
from collections import Counter
from html import escape
import json
from pathlib import Path
import sys
from dashboard_report import DashboardError, MAX_ITEMS, MAX_SIZE, REPO, SCHEMA, SHA, VALID_STATES
from snapshot_metadata import metadata

LABELS = {
    "needs_human_triage": ("תקלה לבדיקה", "failure"),
    "checks_pending": ("בדיקות רצות", "pending"),
    "incomplete_check_evidence": ("ראיות לא שלמות", "warning"),
    "review_gate": ("ממתין לסקירה", "review"),
    "missing_check_evidence": ("חסרות ראיות CI", "warning"),
}
ORDER = ["needs_human_triage", "incomplete_check_evidence",
         "missing_check_evidence", "checks_pending", "review_gate"]


def _check_name(value):
    if not isinstance(value, str):
        return ""
    # HTML escaping + strict length cap protects against markup injection,
    # unreadable giant names and accidental disclosure of untrusted content.
    return escape("".join(c for c in value if c.isprintable())[:70], quote=True)


def render_html(health):
    if not isinstance(health, dict) or health.get("schema") != SCHEMA or health.get("mode") != "observe_only":
        raise DashboardError("invalid_health_snapshot")
    items = health.get("items")
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise DashboardError("invalid_items")
    meta = metadata(health)
    demo = health.get("demo") is True
    counts = Counter()
    rows = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise DashboardError("invalid_item")
        number, sha, state = item.get("pr"), item.get("head_sha"), item.get("state")
        if type(number) is not int or number < 1 or number > 1_000_000 or number in seen:
            raise DashboardError("invalid_or_duplicate_pr")
        if not isinstance(sha, str) or not SHA.fullmatch(sha) or state not in LABELS:
            raise DashboardError("invalid_pr_evidence")
        seen.add(number)
        counts[state] += 1
        label, color = LABELS[state]
        checks = item.get("failed_checks", [])
        if not isinstance(checks, list):
            raise DashboardError("invalid_check_names")
        names = ", ".join(_check_name(n) for n in checks[:3] if isinstance(n, str))
        if not names:
            names = "—"
        url = f"https://github.com/{REPO}/pull/{number}"
        link = (f'<span>דוגמה #{number}</span>' if demo else
                f'<a href="{url}" rel="noopener noreferrer">PR #{number}</a>')
        rows.append(
            f'<tr><td>{link}</td>'
            f'<td><span class="status {color}">{label}</span></td>'
            f'<td dir="ltr"><code>{sha[:10]}</code></td>'
            f'<td class="checks">{names}</td></tr>'
        )
    cards = "\n".join(
        f'<div class="metric"><span>{LABELS[s][0]}</span><strong>{counts[s]}</strong></div>'
        for s in ORDER
    )
    rows_html = "\n".join(rows) or '<tr><td colspan="4">לא נמצאו Pull Requests לבדיקה.</td></tr>'
    demo_notice = ('<p class="demo-warning" role="status">דמו סינתטי בלבד · אין כאן נתוני GitHub חיים, תקלות אמיתיות או אישורי ביצוע.</p>' if demo else '')
    coverage_notice = ('<p class="demo-warning" role="status">דוח חלקי: המעקב מוגבל ל־20 בקשות שינוי. אין להסיק שיתר ה־PRs נבדקו.</p>'
                       if health.get("coverage") == "partial" else '')
    source_notice = ('<p class="snapshot-note">מקור: ' + meta["source_label"] +
                     ' · מועד צילום: ' + (meta["observed_at"] or 'לא צוין') +
                     ' · הדוח סטטי ואינו מתעדכן מעצמו.</p>')
    freshness_notice = ('<p class="demo-warning" role="status">הנתונים היו בני יותר מ־15 דקות בעת יצירת הקובץ. יש לרענן את הבדיקה לפני החלטה.</p>'
                        if meta["freshness"] == "stale_at_render" else
                        '<p class="demo-warning" role="status">זמן צילום לא אומת. אין לראות בדוח מצב חי.</p>'
                        if meta["freshness"] == "unknown" else '')
    return f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; img-src 'none'">
<title>Core8-AI · בקרת פיתוח</title>
<style>
:root{{--bg:#0b1220;--panel:#151f32;--border:#2a3a52;--text:#f4f7fc;--muted:#b3c0d1;--accent:#70a7f7}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.65 system-ui,Arial,sans-serif}}
main{{max-width:1120px;padding:40px 20px 70px;margin:auto}}h1{{font-size:clamp(1.55rem,3vw,2.6rem);margin:0 0 7px}}h2{{font-size:1.2rem;margin:32px 0 12px}}
p{{color:var(--muted);margin:4px 0 18px}}.kicker{{color:var(--accent);font-size:.85rem;font-weight:700;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(156px,1fr));gap:12px;margin-top:28px}}
.metric{{background:var(--panel);border:1px solid var(--border);border-radius:13px;padding:15px;min-height:116px;display:flex;flex-direction:column;justify-content:space-between}}
.metric span{{color:var(--muted);font-size:.84rem}}.metric strong{{font-size:2.1rem;font-variant-numeric:tabular-nums}}
.panel{{background:var(--panel);border:1px solid var(--border);border-radius:14px;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;min-width:650px}}th,td{{padding:13px 17px;text-align:right;border-bottom:1px solid var(--border)}}
th{{color:var(--muted);font-size:.82rem}}tr:last-child td{{border-bottom:0}}a{{color:#9ec7ff;text-decoration:underline}}a:focus{{outline:2px solid #fff}}
.status{{padding:4px 9px;border-radius:100px;background:#25344a;display:inline-block;white-space:nowrap}}
.failure{{color:#ffaaaa}}.warning{{color:#ffdf9b}}.pending{{color:#c8c0ff}}.review{{color:#9ee7bf}}
.checks{{max-width:360px;overflow-wrap:anywhere}}code{{font-family:ui-monospace,monospace;font-size:.86rem}}
footer{{color:var(--muted);border-top:1px solid var(--border);margin-top:35px;padding-top:18px;font-size:.85rem}}
.snapshot-note{{font-size:.85rem;color:var(--muted)}}
.demo-warning{{background:#3d291e;border:1px solid #f6bb75;color:#ffe0b5;padding:12px 16px;border-radius:10px;font-weight:700}}
</style>
</head>
<body>
<main>
<div class="kicker">CORE8-AI · ENGINEERING CONTROL</div>
<h1>מרכז בקרת הפיתוח</h1>
<p>תמונת מצב לצפייה בלבד; הצלחת בדיקה אינה אישור למיזוג, פריסה או חיוב כספי.</p>
{demo_notice}
{coverage_notice}
{freshness_notice}
{source_notice}
<section class="metrics" aria-label="סיכום סטטוסים">{cards}</section>
<h2>בדיקות Pull Requests · {len(items)} פריטים</h2>
<div class="panel"><table>
<thead><tr><th scope="col">בקשת שינוי</th><th scope="col">מצב CI</th><th scope="col">גרסה</th><th scope="col">בדיקות שנכשלו</th></tr></thead>
<tbody>{rows_html}</tbody>
</table></div>
<footer>מקור: {("נתונים סינתטיים בלבד" if demo else "GitHub checks")}. מידע אישי, אישורי Notion, סודות ונתוני לקוחות אינם משולבים בדוח.
אין כאן ריצה אוטונומית של Claude Code או עדכון לסטטוס משימות.</footer>
</main>
</body>
</html>
"""


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: browser_dashboard.py core8-dev-loop-report.json")
    try:
        path = Path(sys.argv[1])
        if not path.is_file() or path.stat().st_size > MAX_SIZE:
            raise DashboardError("invalid_input_file")
        result = render_html(json.loads(path.read_text(encoding="utf-8")))
        Path("core8-dev-loop-dashboard.html").write_text(result, encoding="utf-8")
        print("core8_browser_dashboard_generated mode=observe_only")
    except (OSError, UnicodeError, ValueError):
        print("core8_browser_dashboard_rejected", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
