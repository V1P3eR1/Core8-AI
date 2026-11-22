import hashlib
import unittest
from datetime import datetime, timezone
from artifact_receipt import RejectedArtifact, validate_artifact_receipt


class ArtifactReceiptTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
        self.patch = b"diff --git a/docs/a.md b/docs/a.md\n"
        self.receipt = {
            "repo": "V1P3eR1/Core8-AI", "run_id": 123, "artifact_id": 456,
            "head_sha": "a" * 40, "task_digest": "b" * 64,
            "task_revision": 1, "issue_number": 62, "approver_id": 999,
            "run_event": "issue_comment", "run_conclusion": "success",
            "artifact_name": "core8-implementation-patch", "expired": False,
            "artifact_sha256": hashlib.sha256(self.patch).hexdigest(),
            "created_at": "2026-11-22T10:00:00Z",
            "expires_at": "2026-11-29T10:00:00Z",
        }
        self.expected = {k: self.receipt[k] for k in (
            "repo", "run_id", "artifact_id", "head_sha", "task_digest",
            "task_revision", "issue_number", "approver_id", "run_event",
            "run_conclusion", "artifact_name", "expired", "artifact_sha256",
            "created_at", "expires_at")}
        self.expected.update(decision="Approved", public_export=True, execution_authorized=True)

    def check(self, **changes):
        receipt = self.receipt.copy()
        receipt.update(changes)
        return validate_artifact_receipt(receipt=receipt, expected_record=self.expected,
                                         patch_bytes=self.patch, now=self.now, consumed=set())

    def test_valid(self):
        self.assertEqual(self.check()["artifact_key"], ("V1P3eR1/Core8-AI", 123, 456))

    def test_wrong_run(self):
        with self.assertRaises(RejectedArtifact): self.check(run_id=124)

    def test_wrong_issue(self):
        with self.assertRaises(RejectedArtifact): self.check(issue_number=999)

    def test_wrong_task_digest(self):
        with self.assertRaises(RejectedArtifact): self.check(task_digest="c" * 64)

    def test_wrong_approver(self):
        with self.assertRaises(RejectedArtifact): self.check(approver_id=1000)

    def test_wrong_revision(self):
        with self.assertRaises(RejectedArtifact): self.check(task_revision=2)

    def test_wrong_head_commit(self):
        with self.assertRaises(RejectedArtifact): self.check(head_sha="d" * 40)

    def test_untrusted_repo(self):
        with self.assertRaises(RejectedArtifact): self.check(repo="another/repo")

    def test_wrong_event(self):
        with self.assertRaises(RejectedArtifact): self.check(run_event="push")

    def test_failed_run(self):
        with self.assertRaises(RejectedArtifact): self.check(run_conclusion="failure")

    def test_fake_artifact_name(self):
        with self.assertRaises(RejectedArtifact): self.check(artifact_name="other")

    def test_expired_flag(self):
        with self.assertRaises(RejectedArtifact): self.check(expired=True)

    def test_digest_mismatch(self):
        with self.assertRaises(RejectedArtifact): self.check(artifact_sha256="0" * 64)

    def test_expired_time(self):
        with self.assertRaises(RejectedArtifact): self.check(expires_at="2026-11-22T11:00:00Z")

    def test_future_creation(self):
        with self.assertRaises(RejectedArtifact): self.check(created_at="2026-11-22T13:00:00Z")

    def test_invalid_timestamp(self):
        with self.assertRaises(RejectedArtifact): self.check(created_at="yesterday")

    def test_replay(self):
        with self.assertRaises(RejectedArtifact):
            validate_artifact_receipt(receipt=self.receipt, expected_record=self.expected,
                                      patch_bytes=self.patch, now=self.now,
                                      consumed={("V1P3eR1/Core8-AI", 123, 456)})

    def test_not_approved(self):
        e = self.expected.copy()
        e["decision"] = "Proposal"
        with self.assertRaises(RejectedArtifact):
            validate_artifact_receipt(receipt=self.receipt, expected_record=e,
                                      patch_bytes=self.patch, now=self.now, consumed=set())

    def test_public_export_denied(self):
        e = self.expected.copy()
        e["public_export"] = False
        with self.assertRaises(RejectedArtifact):
            validate_artifact_receipt(receipt=self.receipt, expected_record=e,
                                      patch_bytes=self.patch, now=self.now, consumed=set())

    def test_execution_denied(self):
        e = self.expected.copy()
        e["execution_authorized"] = False
        with self.assertRaises(RejectedArtifact):
            validate_artifact_receipt(receipt=self.receipt, expected_record=e,
                                      patch_bytes=self.patch, now=self.now, consumed=set())

    def test_self_reported_digest_does_not_override_trusted_digest(self):
        # Attacker's payload and SHA are consistent, but not independently trusted.
        forged = b"diff --git a/docs/forged.md b/docs/forged.md\n"
        receipt = self.receipt.copy()
        receipt["artifact_sha256"] = hashlib.sha256(forged).hexdigest()
        with self.assertRaisesRegex(RejectedArtifact, "provenance_mismatch"):
            validate_artifact_receipt(
                receipt=receipt, expected_record=self.expected, patch_bytes=forged,
                now=self.now, consumed=set())

    def test_self_reported_success_cannot_rewrite_failure(self):
        expected = self.expected.copy()
        expected["run_conclusion"] = "failure"
        with self.assertRaisesRegex(RejectedArtifact, "provenance_mismatch"):
            validate_artifact_receipt(
                receipt=self.receipt, expected_record=expected,
                patch_bytes=self.patch, now=self.now, consumed=set())

    def test_self_reported_expiry_cannot_extend_retention(self):
        expected = self.expected.copy()
        expected["expires_at"] = "2026-11-22T11:00:00Z"
        with self.assertRaisesRegex(RejectedArtifact, "provenance_mismatch"):
            validate_artifact_receipt(
                receipt=self.receipt, expected_record=expected,
                patch_bytes=self.patch, now=self.now, consumed=set())

    def test_missing_independently_trusted_digest_fails_closed(self):
        expected = self.expected.copy()
        del expected["artifact_sha256"]
        with self.assertRaisesRegex(RejectedArtifact, "missing_metadata"):
            validate_artifact_receipt(
                receipt=self.receipt, expected_record=expected,
                patch_bytes=self.patch, now=self.now, consumed=set())

    def test_missing_field(self):
        r = self.receipt.copy()
        del r["artifact_id"]
        with self.assertRaises(RejectedArtifact):
            validate_artifact_receipt(receipt=r, expected_record=self.expected,
                                      patch_bytes=self.patch, now=self.now, consumed=set())


    def test_forged_success_after_failed_run(self):
        self.expected["run_conclusion"] = "failure"
        with self.assertRaisesRegex(RejectedArtifact, "provenance_mismatch"):
            self.check()

    def test_forged_artifact_name(self):
        self.expected["artifact_name"] = "different-artifact"
        with self.assertRaisesRegex(RejectedArtifact, "provenance_mismatch"):
            self.check()

    def test_forged_expiry(self):
        self.expected["expires_at"] = "2026-11-22T11:00:00Z"
        with self.assertRaisesRegex(RejectedArtifact, "provenance_mismatch"):
            self.check()

    def test_forged_digest_with_matching_payload(self):
        payload = b"attacker-controlled-patch"
        receipt = self.receipt.copy()
        receipt["artifact_sha256"] = hashlib.sha256(payload).hexdigest()
        with self.assertRaisesRegex(RejectedArtifact, "provenance_mismatch"):
            validate_artifact_receipt(receipt=receipt, expected_record=self.expected,
                                      patch_bytes=payload, now=self.now, consumed=set())

    def test_forged_created_at(self):
        self.expected["created_at"] = "2026-11-21T10:00:00Z"
        with self.assertRaisesRegex(RejectedArtifact, "provenance_mismatch"):
            self.check()


if __name__ == "__main__":
    unittest.main()
