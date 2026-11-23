"""Synthetic tests for Core8 private local-only status summaries."""
import unittest

from private_task_summary import summarize, PrivateSummaryError

TASK = "416fbd9f-57df-81a9-9fb1-c655e72b8052"

def fixture():
    return {
        "schema": "core8-notion-github-readonly-audit-v1",
        "mode": "observe_only",
        "task_count": 2, "linked_task_count": 1, "attention_count": 1,
        "can_change_notion": False,
        "can_export_private_scope": False,
        "can_authorize_claude": False,
        "items": [
            {"task_id": TASK, "issue_number": 20, "notion_status": "Review",
             "github_state": "open", "flags": [], "public_scope_gate": "verified_metadata_only",
             "Scope": "SECRET_SCOPE_DO_NOT_EXPORT", "approval_evidence": "secret-approval"},
            {"task_id": "11111111-2222-3333-4444-555555555555",
             "issue_number": None, "notion_status": "Awaiting approval",
             "github_state": "not_linked",
             "flags": ["public_export_disabled", "public_scope_gate_incomplete"],
             "public_scope_gate": "blocked",
             "Acceptance": "SENSITIVE_CUSTOMER_DATA"},
        ],
    }


class PrivateSummaryTests(unittest.TestCase):
    def test_aggregation_contains_no_private_identifiers_or_text(self):
        result = summarize(fixture())
        self.assertEqual(result["scope"], "private_local_only")
        self.assertEqual(result["tasks"], 2)
        self.assertEqual(result["status_counts"]["Review"], 1)
        self.assertEqual(result["status_counts"]["Awaiting approval"], 1)
        self.assertEqual(result["diagnostic_counts"]["public_export_disabled"], 1)
        for bad in ("SECRET_SCOPE_DO_NOT_EXPORT", "SENSITIVE_CUSTOMER_DATA",
                    TASK, "secret-approval", '"20"'):
            self.assertNotIn(bad, str(result))
        self.assertFalse(result["may_publish_to_public_ci"])
        self.assertFalse(result["may_authorize_claude"])

    def test_unsafe_permissions_refused(self):
        for key in ("can_change_notion", "can_export_private_scope", "can_authorize_claude"):
            x = fixture()
            x[key] = True
            with self.assertRaises(PrivateSummaryError):
                summarize(x)

    def test_unknown_flags_fail_closed(self):
        x = fixture()
        x["items"][1]["flags"] = ["secret" ]
        with self.assertRaises(PrivateSummaryError):
            summarize(x)

    def test_inconsistent_count_refused(self):
        for key in ("task_count", "linked_task_count", "attention_count"):
            x = fixture()
            x[key] += 1
            with self.assertRaises(PrivateSummaryError):
                summarize(x)

    def test_duplicate_issue_and_task_refused(self):
        x = fixture()
        x["items"][1]["issue_number"] = 20
        x["linked_task_count"] = 2
        with self.assertRaises(PrivateSummaryError):
            summarize(x)
        x = fixture()
        x["items"][1]["task_id"] = TASK
        with self.assertRaises(PrivateSummaryError):
            summarize(x)

    def test_unknown_states_and_gate_refused(self):
        for key, value in (("notion_status", "publish"), ("github_state", "deployed"),
                           ("public_scope_gate", "approved_for_execution")):
            x = fixture()
            x["items"][1][key] = value
            with self.assertRaises(PrivateSummaryError):
                summarize(x)

    def test_empty_audit_allowed(self):
        x = fixture()
        x["items"] = []
        x["task_count"] = 0
        x["linked_task_count"] = 0
        x["attention_count"] = 0
        result = summarize(x)
        self.assertEqual(result["tasks"], 0)
        self.assertEqual(result["status_counts"], {})


if __name__ == "__main__":
    unittest.main()
