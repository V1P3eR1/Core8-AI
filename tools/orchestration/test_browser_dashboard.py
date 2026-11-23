"""Contract tests for standalone offline RTL CI dashboard."""
import unittest
from browser_dashboard import render_html
from dashboard_report import DashboardError

SHA = "a" * 40

def sample(items=None):
    return {"schema": "core8-dev-loop-health-v1", "mode": "observe_only",
            "items": items if items is not None else []}

def pr(number=61, state="review_gate", check="ci"):
    return {"pr": number, "head_sha": SHA, "state": state, "failed_checks": [check]}

class BrowserDashboardTests(unittest.TestCase):
    def test_rtl_standalone_and_pr_link(self):
        html = render_html(sample([pr()]))
        self.assertIn('lang="he" dir="rtl"', html)
        self.assertIn("https://github.com/V1P3eR1/Core8-AI/pull/61", html)
        self.assertIn("בקרת הפיתוח", html)
        self.assertNotIn("<script", html)
        self.assertIn("default-src 'none'", html)

    def test_untrusted_check_name_escaped(self):
        html = render_html(sample([pr(check='<img src=x onerror=alert(1)> " & \\n|')]))
        self.assertNotIn("<img", html)
        self.assertNotIn('<img src=x onerror=', html)
        self.assertIn("&lt;img", html)
        self.assertIn("&amp;", html)

    def test_html_never_includes_private_notion_data(self):
        obj = sample([pr()])
        obj["private_notion"] = {"scope": "PRIVATE_DO_NOT_PUBLISH", "token": "secret"}
        html = render_html(obj)
        self.assertNotIn("PRIVATE_DO_NOT_PUBLISH", html)
        self.assertNotIn('"token"', html)
        self.assertIn("מידע אישי", html)

    def test_all_states_render(self):
        states = ["needs_human_triage", "checks_pending", "incomplete_check_evidence",
                  "review_gate", "missing_check_evidence"]
        html = render_html(sample([pr(i + 1, state) for i, state in enumerate(states)]))
        for state in states:
            self.assertIn("1</strong>", html)

    def test_invalid_schema_or_execution_mode_fails_closed(self):
        obj = sample()
        obj["mode"] = "auto_execute"
        with self.assertRaises(DashboardError):
            render_html(obj)

    def test_duplicate_pr_and_untrusted_sha_refused(self):
        with self.assertRaises(DashboardError):
            render_html(sample([pr(), pr()]))
        bad = pr()
        bad["head_sha"] = "x"
        with self.assertRaises(DashboardError):
            render_html(sample([bad]))

    def test_no_prs_has_empty_state(self):
        self.assertIn("לא נמצאו Pull Requests", render_html(sample()))

    def test_too_many_rows_refused(self):
        with self.assertRaises(DashboardError):
            render_html(sample([pr(i + 1) for i in range(61)]))

if __name__ == "__main__":
    unittest.main()
