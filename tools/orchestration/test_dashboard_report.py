"""Read-only engineering dashboard contract and injection tests."""
import unittest
from dashboard_report import render, DashboardError

SHA = "a" * 40

def report(items=None):
    return {"schema": "core8-dev-loop-health-v1", "mode": "observe_only",
            "items": [] if items is None else items}

def item(n=31, state="needs_human_triage", checks=None, sha=SHA):
    return {"pr": n, "state": state, "head_sha": sha,
            "failed_checks": [] if checks is None else checks}

class DashboardTests(unittest.TestCase):
    def test_readonly_status_and_pr_links(self):
        text = render(report([item()]))
        self.assertIn("https://github.com/V1P3eR1/Core8-AI/pull/31", text)
        self.assertIn("Failure needs triage: 1", text)
        self.assertIn("Not checked by this GitHub Actions report", text)
        self.assertIn("no autonomous model calls", text)

    def test_failing_check_names_are_markdown_and_html_escaped(self):
        text = render(report([item(checks=["<script>alert(1)</script>|\\n[steal](http://evil.example)"])]))
        self.assertNotIn("<script>", text)
        self.assertNotIn("http://evil.example", text)
        self.assertNotIn("[steal]", text)
        self.assertNotIn("|\\n[", text)

    def test_no_private_details_in_optional_notion_summary(self):
        notion = {"schema": "core8-notion-github-readonly-audit-v1",
                  "mode": "observe_only", "can_change_notion": False,
                  "task_count": 9, "linked_task_count": 3, "attention_count": 6,
                  "items": [{"Scope": "SECRET CLIENT DATA", "task_id": "private"}]}
        text = render(report(), notion)
        self.assertIn("Tasks inspected: 9", text)
        self.assertIn("Linked GitHub issues: 3", text)
        self.assertNotIn("SECRET CLIENT DATA", text)

    def test_malformed_git_status_fails_closed(self):
        with self.assertRaises(DashboardError):
            render(report([item(state="all_green")]))
        with self.assertRaises(DashboardError):
            render(report([item(sha="malformed")]))

    def test_duplicate_pr_fails_closed(self):
        with self.assertRaises(DashboardError):
            render(report([item(), item()]))

    def test_unknown_or_enabled_mode_fails_closed(self):
        bad = report()
        bad["mode"] = "auto_execute"
        with self.assertRaises(DashboardError):
            render(bad)

    def test_unsafe_notion_summary_denied(self):
        with self.assertRaises(DashboardError):
            render(report(), {"schema": "core8-notion-github-readonly-audit-v1",
                              "mode": "observe_only", "can_change_notion": True,
                              "task_count": 0, "linked_task_count": 0, "attention_count": 0})

    def test_no_status_when_no_prs(self):
        text = render(report())
        self.assertIn("No tracked pull requests", text)
        self.assertIn("Review pending/blocked evidence", text)

    def test_bad_notion_counts_denied(self):
        with self.assertRaises(DashboardError):
            render(report(), {"schema": "core8-notion-github-readonly-audit-v1",
                              "mode": "observe_only", "can_change_notion": False,
                              "task_count": 2, "linked_task_count": 3, "attention_count": 0})

if __name__ == "__main__":
    unittest.main()
