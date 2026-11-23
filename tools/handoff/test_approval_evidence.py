import hashlib
import unittest
from approval_evidence import (verify_issue_comment, fetch_verified_issue_comment, PREFIX)
from github_provenance import EvidenceBlocked

TASK = "11111111-2222-4333-8444-555555555555"
DIGEST = "a" * 64


class FakeReader:
    def __init__(self, issue, comment):
        self.issue, self.comment, self.paths = issue, comment, []
    def _get(self, path):
        self.paths.append(path)
        if path == "issues/62": return self.issue
        if path == "issues/comments/456": return self.comment
        raise AssertionError("unexpected path")


class ApprovalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.body = ("Core8 implementation intake.\n<!-- core8-task:" + TASK +
                     " -->\nScope SHA256: " + chr(96) + DIGEST + chr(96) + "\n")
        self.issue = {"number": 62, "state": "open", "body": self.body}
        self.comment = {"id": 456, "issue_url": PREFIX + "62",
                        "body": "/core8-implement " + DIGEST,
                        "user": {"id": 999, "type": "User"},
                        "created_at": "2026-11-23T08:00:00Z",
                        "updated_at": "2026-11-23T08:00:00Z"}
    def verify(self):
        return verify_issue_comment(
            self.issue, self.comment, issue_number=62, comment_id=456,
            approver_id=999, task_uuid=TASK, task_digest=DIGEST,
            expected_issue_body_sha256=hashlib.sha256(self.body.encode()).hexdigest())

    def test_valid(self): self.assertEqual(self.verify()["approver_id"], 999)
    def test_fixed_read_only_paths(self):
        reader = FakeReader(self.issue, self.comment)
        self.assertEqual(fetch_verified_issue_comment(
            reader, issue_number=62, comment_id=456, approver_id=999,
            task_uuid=TASK, task_digest=DIGEST,
            expected_issue_body_sha256=hashlib.sha256(self.body.encode()).hexdigest())["comment_id"], 456)
        self.assertEqual(reader.paths, ["issues/62", "issues/comments/456"])
    def test_edited_comment(self):
        self.comment["updated_at"] = "2026-11-23T09:00:00Z"
        with self.assertRaises(EvidenceBlocked): self.verify()
    def test_wrong_author(self):
        self.comment["user"]["id"] = 888
        with self.assertRaises(EvidenceBlocked): self.verify()
    def test_bot(self):
        self.comment["user"]["type"] = "Bot"
        with self.assertRaises(EvidenceBlocked): self.verify()
    def test_app_comment(self):
        self.comment["performed_via_github_app"] = True
        with self.assertRaises(EvidenceBlocked): self.verify()
    def test_wrong_issue(self):
        self.comment["issue_url"] = PREFIX + "70"
        with self.assertRaises(EvidenceBlocked): self.verify()
    def test_modified_issue_body(self):
        self.issue["body"] += "tampered"
        with self.assertRaisesRegex(EvidenceBlocked, "issue_scope_changed"): self.verify()
    def test_closed_issue(self):
        self.issue["state"] = "closed"
        with self.assertRaises(EvidenceBlocked): self.verify()
    def test_pull_request_issue(self):
        self.issue["pull_request"] = {"url": "fake"}
        with self.assertRaises(EvidenceBlocked): self.verify()
    def test_wrong_digest(self):
        self.comment["body"] = "/core8-implement " + "b" * 64
        with self.assertRaises(EvidenceBlocked): self.verify()
    def test_duplicate_marker(self):
        self.issue["body"] += "<!-- core8-task:" + TASK + " -->"
        with self.assertRaises(EvidenceBlocked): self.verify()
    def test_boolean_approver_id(self):
        with self.assertRaises(EvidenceBlocked):
            verify_issue_comment(self.issue, self.comment, issue_number=62,
                                 comment_id=456, approver_id=True, task_uuid=TASK,
                                 task_digest=DIGEST,
                                 expected_issue_body_sha256=hashlib.sha256(self.body.encode()).hexdigest())
    def test_bad_id_rejected_before_fetch(self):
        reader = FakeReader(self.issue, self.comment)
        with self.assertRaises(EvidenceBlocked):
            fetch_verified_issue_comment(reader, issue_number="../62",
                                         comment_id=456, approver_id=999,
                                         task_uuid=TASK, task_digest=DIGEST,
                                         expected_issue_body_sha256=hashlib.sha256(self.body.encode()).hexdigest())
        self.assertEqual(reader.paths, [])

if __name__ == "__main__":
    unittest.main()
