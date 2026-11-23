import unittest
from datetime import datetime, timezone
from evidence_binding import bind_review_evidence
from github_provenance import EvidenceBlocked, REPO

NOW = datetime(2026, 11, 23, 10, 30, tzinfo=timezone.utc)
TASK = "11111111-2222-4333-8444-555555555555"


class EvidenceBindingTests(unittest.TestCase):
    def setUp(self):
        self.approval = {
            "repo": REPO, "issue_number": 62, "comment_id": 456,
            "approver_id": 999, "task_uuid": TASK,
            "task_digest": "a" * 64, "issue_body_sha256": "b" * 64}
        self.run = {
            "repo": REPO, "run_id": 123, "artifact_id": 789, "approver_id": 999,
            "head_sha": "c" * 40, "run_conclusion": "success",
            "run_event": "issue_comment", "expired": False,
            "archive_sha256": "d" * 64, "created_at": "2026-11-23T08:10:00Z",
            "expires_at": "2026-11-30T08:10:00Z"}
        self.gate = dict(self.approval, run_id=123, artifact_id=789,
                         head_sha="c" * 40, task_revision=1,
                         approved_at="2026-11-23T08:00:00Z")

    def check(self):
        return bind_review_evidence(self.approval, self.run, self.gate, now=NOW)

    def test_valid_is_review_only(self):
        self.assertEqual(self.check()["status"], "BOUND_FOR_REVIEW_ONLY")
    def test_missing_gate(self):
        with self.assertRaises(EvidenceBlocked):
            bind_review_evidence(self.approval, self.run, None, now=NOW)
    def test_wrong_comment(self):
        self.gate["comment_id"] = 111
        with self.assertRaises(EvidenceBlocked): self.check()
    def test_wrong_run(self):
        self.gate["run_id"] = 999
        with self.assertRaises(EvidenceBlocked): self.check()
    def test_wrong_artifact(self):
        self.gate["artifact_id"] = 999
        with self.assertRaises(EvidenceBlocked): self.check()
    def test_wrong_approver(self):
        self.gate["approver_id"] = 111
        with self.assertRaises(EvidenceBlocked): self.check()
    def test_wrong_task_digest(self):
        self.gate["task_digest"] = "e" * 64
        with self.assertRaises(EvidenceBlocked): self.check()
    def test_wrong_issue_body_hash(self):
        self.gate["issue_body_sha256"] = "f" * 64
        with self.assertRaises(EvidenceBlocked): self.check()
    def test_wrong_head(self):
        self.run["head_sha"] = "e" * 40
        with self.assertRaises(EvidenceBlocked): self.check()
    def test_boolean_revision(self):
        self.gate["task_revision"] = True
        with self.assertRaises(EvidenceBlocked): self.check()
    def test_unexpected_gate_key(self):
        self.gate["override"] = True
        with self.assertRaises(EvidenceBlocked): self.check()
    def test_approval_after_creation(self):
        self.gate["approved_at"] = "2026-11-23T09:00:00Z"
        with self.assertRaises(EvidenceBlocked): self.check()
    def test_expired_artifact(self):
        self.run["expires_at"] = "2026-11-23T09:00:00Z"
        with self.assertRaises(EvidenceBlocked): self.check()
    def test_naive_datetime(self):
        with self.assertRaises(EvidenceBlocked):
            bind_review_evidence(self.approval, self.run, self.gate, now=datetime(2026, 11, 23))
    def test_failed_run(self):
        self.run["run_conclusion"] = "failure"
        with self.assertRaises(EvidenceBlocked): self.check()
    def test_no_publish_authority(self):
        self.assertNotIn("publish_authorized", self.check())

if __name__ == "__main__":
    unittest.main()
