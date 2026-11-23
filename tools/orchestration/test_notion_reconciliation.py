"""Synthetic Notion/GitHub reconciliation contracts; no external access."""
import unittest
from notion_reconciliation import reconcile, ReconciliationError

UUID = "416fbd9f-57df-81a9-9fb1-c655e72b8052"

def task(task_id=UUID, issue=20, state="Review", decision="Approved", exported=True, evidence=True):
    return {"id": task_id, "properties": {
        "Decision": {"select": {"name": decision}},
        "Status": {"select": {"name": state}},
        "Public export": {"checkbox": exported},
        "Approval evidence": {"url": "https://notion.so/private-approval" if evidence else None},
        "GitHub issue": {"url": f"https://github.com/V1P3eR1/Core8-AI/issues/{issue}" if issue else None},
        "Scope": {"rich_text": [{"plain_text": "PRIVATE SYNTHETIC SCOPE DO NOT EXPORT"}]},
        "Acceptance": {"rich_text": [{"plain_text": "PRIVATE SYNTHETIC ACCEPTANCE"}]},
    }}

def issue(task_id=UUID, state="open", body=None):
    return {"state": state, "body": body or f"<!-- core8-task:{task_id} -->\nSynthetic issue", "title": "Public fixture"}

class ReconciliationTests(unittest.TestCase):
    def test_valid_existing_link_does_not_grant_execution(self):
        result = reconcile([task()], {20: issue()})
        self.assertEqual(result["linked_task_count"], 1)
        self.assertEqual(result["items"][0]["github_state"], "open")
        self.assertEqual(result["items"][0]["flags"], [])
        self.assertFalse(result["can_authorize_claude"])
        self.assertFalse(result["can_change_notion"])
        self.assertFalse(result["can_export_private_scope"])

    def test_approved_but_not_public_must_not_export(self):
        result = reconcile([task(exported=False)], {20: issue()})
        row = result["items"][0]
        self.assertIn("existing_link_not_new_export_permission", row["flags"])
        self.assertEqual(row["public_scope_gate"], "blocked")
        self.assertNotIn("PRIVATE SYNTHETIC", str(result))

    def test_missing_approval_evidence_blocks(self):
        row = reconcile([task(evidence=False)], {20: issue()})["items"][0]
        self.assertIn("public_scope_gate_incomplete", row["flags"])

    def test_proposal_never_implicitly_approved(self):
        row = reconcile([task(decision="Proposal")], {20: issue()})["items"][0]
        self.assertIn("decision_not_approved", row["flags"])

    def test_unlinked_private_task_never_creates_issue(self):
        report = reconcile([task(issue=None, exported=False)], {})
        self.assertEqual(report["items"][0]["github_state"], "not_linked")
        self.assertEqual(report["linked_task_count"], 0)

    def test_stale_or_inaccessible_issue_evidence_detected(self):
        flags = reconcile([task()], {})["items"][0]["flags"]
        self.assertIn("issue_evidence_missing", flags)

    def test_closed_issue_is_not_auto_acceptance(self):
        row = reconcile([task(state="In progress")], {20: issue(state="closed")})["items"][0]
        self.assertIn("closed_issue_needs_review", row["flags"])

    def test_reopened_issue_is_not_hidden(self):
        row = reconcile([task(state="Closed - unverified")], {20: issue()})["items"][0]
        self.assertIn("reopened_issue_needs_review", row["flags"])

    def test_mismatched_marker_blocks_mapping(self):
        row = reconcile([task()], {20: issue(task_id="11111111-2222-3333-4444-555555555555")})["items"][0]
        self.assertIn("scope_mapping_mismatch", row["flags"])
        self.assertEqual(row["github_state"], "invalid")

    def test_duplicate_and_pr_rejection(self):
        with self.assertRaises(ReconciliationError):
            reconcile([task(), task()], {20: issue()})
        second = task(task_id="11111111-2222-3333-4444-555555555555")
        with self.assertRaises(ReconciliationError):
            reconcile([task(), second], {20: issue()})
        row = reconcile([task()], {20: {**issue(), "pull_request": {"url": "synthetic"}}})["items"][0]
        self.assertIn("linked_record_is_pr", row["flags"])

    def test_external_issue_domain_denied(self):
        row = task()
        row["properties"]["GitHub issue"]["url"] = "https://evil.example/issues/20"
        with self.assertRaises(ReconciliationError):
            reconcile([row], {})

    def test_private_scope_omitted_even_if_approved(self):
        report = reconcile([task()], {20: issue()})
        self.assertNotIn("PRIVATE SYNTHETIC SCOPE DO NOT EXPORT", str(report))
        self.assertNotIn("private-approval", str(report))

if __name__ == "__main__":
    unittest.main()
