"""Local-only private dashboard: privacy and fail-closed tests."""
import unittest
from dashboard_report import DashboardError
from private_dashboard import private_html

def notion():
    return {
        "schema": "core8-private-metadata-summary-v1", "scope": "private_local_only",
        "mode": "observe_only", "tasks": 9, "linked_issues": 3,
        "needs_review": 7, "status_counts": {"Awaiting approval": 7, "Review": 1,
                                           "Closed - unverified": 1},
        "may_publish_to_public_ci": False, "may_write_to_notion": False,
        "may_authorize_claude": False,
        "leaked_scope": "PRIVATE_CLIENT_SECRET",
        "task_id": "DO_NOT_EXPORT",
    }

def github():
    return {"schema": "core8-dev-loop-health-v1", "mode": "observe_only",
            "items": [{"state": "review_gate", "title": "CUSTOMER_PRIVATE_NAME"},
                      {"state": "checks_pending", "body": "PRIVATE_ISSUE_BODY"}]}

class PrivateDashboardTests(unittest.TestCase):
    def test_offline_private_dashboard_renders_aggregate_only(self):
        html = private_html(notion(), github())
        self.assertIn('lang="he" dir="rtl"', html)
        self.assertIn("Awaiting approval", html)
        self.assertIn("9</strong>", html)
        self.assertIn("7 דורשות בדיקה", html)
        self.assertIn("GitHub", html)
        self.assertNotIn("<script", html)
        for value in ["PRIVATE_CLIENT_SECRET", "DO_NOT_EXPORT",
                      "CUSTOMER_PRIVATE_NAME", "PRIVATE_ISSUE_BODY"]:
            self.assertNotIn(value, html)

    def test_public_export_is_forbidden(self):
        n = notion()
        n["may_publish_to_public_ci"] = True
        with self.assertRaises(DashboardError):
            private_html(n, github())

    def test_other_authorizations_are_forbidden(self):
        for key in ("may_write_to_notion", "may_authorize_claude"):
            n = notion()
            n[key] = True
            with self.assertRaises(DashboardError):
                private_html(n, github())

    def test_untrusted_status_and_inconsistent_totals_denied(self):
        n = notion()
        n["status_counts"]["<img src=x>"] = 1
        with self.assertRaises(DashboardError):
            private_html(n, github())
        n = notion()
        n["tasks"] = 8
        with self.assertRaises(DashboardError):
            private_html(n, github())

    def test_missing_count_and_bad_github_state_denied(self):
        n = notion()
        del n["linked_issues"]
        with self.assertRaises(DashboardError):
            private_html(n, github())
        g = github()
        g["items"][0]["state"] = "merged_automatically"
        with self.assertRaises(DashboardError):
            private_html(notion(), g)

if __name__ == "__main__":
    unittest.main()
