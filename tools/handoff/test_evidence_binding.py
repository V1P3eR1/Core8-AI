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
            "task_digest": "a" * 64, "issue_body_sha256": "b" * 64,
            "comment_created_at": "2026-11-23T08:05:00Z"}
        self.run = {
            "repo": REPO, "run_id": 123, "artifact_id": 789, "approver_id": 999,
            "head_sha": "c" * 40, "run_conclusion": "success",
            "run_event": "issue_comment", "expired": False,
            "archive_sha256": "d" * 64, "created_at": "2026-11-23T08:10:00Z",
            "expires_at": "2026-11-30T08:10:00Z"}
        self.gate = dict({key: value for key, value in self.approval.items()
                          if key != "comment_created_at"},
                         run_id=123, artifact_id=789, head_sha="c" * 40,
                         task_revision=1, approved_at="2026-11-23T08:00:00Z")

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
    def test_comment_after_artifact_creation_is_rejected(self):
        self.approval["comment_created_at"] = "2026-11-23T08:20:00Z"
        with self.assertRaisesRegex(EvidenceBlocked, "approval_or_artifact_time_mismatch"):
            self.check()

    def test_comment_before_private_approval_is_rejected(self):
        self.approval["comment_created_at"] = "2026-11-23T07:59:59Z"
        with self.assertRaisesRegex(EvidenceBlocked, "approval_or_artifact_time_mismatch"):
            self.check()

    def test_missing_comment_creation_time_is_rejected(self):
        self.approval.pop("comment_created_at")
        with self.assertRaisesRegex(EvidenceBlocked, "invalid_provenance_time"):
            self.check()

    def test_malformed_comment_creation_time_is_rejected(self):
        self.approval["comment_created_at"] = "2026-11-23T08:05:00+03:00"
        with self.assertRaisesRegex(EvidenceBlocked, "invalid_provenance_time"):
            self.check()

    def test_comment_between_approval_and_artifact_accepted(self):
        self.assertEqual(self.check()["status"], "BOUND_FOR_REVIEW_ONLY")

    def test_approval_after_creation(self):
        self.gate["approved_at"] = "2026-11-23T09:00:00Z"
        with self.assertRaises(EvidenceBlocked): self.check()
    def test_ambiguous_or_malformed_evidence_times_block(self):
        invalid = ("2026-11-23 08:00:00Z", "2026-11-23T08:00:00+00:00",
                   "2026-02-30T08:00:00Z", "2026-11-23T25:00:00Z",
                   "2026-11-23T08:00:00.1234567890Z")
        for value in invalid:
            with self.subTest(value=value):
                self.gate["approved_at"] = value
                with self.assertRaisesRegex(EvidenceBlocked, "invalid_provenance_time"):
                    self.check()
        self.gate["approved_at"] = "2026-11-23T08:00:00Z"
        self.run["created_at"] = "2026-11-23 08:10:00Z"
        with self.assertRaisesRegex(EvidenceBlocked, "invalid_provenance_time"):
            self.check()

    def test_fractional_utc_evidence_is_accepted(self):
        self.gate["approved_at"] = "2026-11-23T08:00:00.123456Z"
        self.assertEqual(self.check()["status"], "BOUND_FOR_REVIEW_ONLY")

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
