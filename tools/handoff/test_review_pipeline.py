import hashlib
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from review_pipeline import ReviewRejected, stage_review
from replay_ledger import ReplayBlocked

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.checkout = self.base / "checkout"
        self.checkout.mkdir()
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
        (self.checkout / "docs").mkdir()
        self.patch = (b"diff --git a/docs/demo.md b/docs/demo.md\n"
                      b"new file mode 100644\nindex 0000000..1234567\n"
                      b"--- /dev/null\n+++ b/docs/demo.md\n"
                      b"@@ -0,0 +1 @@\n+hello\n")
        self.now = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
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
        self.expected = dict(self.receipt)
        self.expected.update(decision="Approved", public_export=True,
                             execution_authorized=True)
        self.ledger_path = self.base / "replay.db"

    def run_pipeline(self, patch=None, receipt=None, expected=None):
        return stage_review(
            receipt=self.receipt if receipt is None else receipt,
            expected_record=self.expected if expected is None else expected,
            patch_bytes=self.patch if patch is None else patch,
            now=self.now, ledger_path=self.ledger_path,
            checkout_path=self.checkout)

    def test_good_patch_only_reserved(self):
        result = self.run_pipeline()
        self.assertEqual(result["status"], "RESERVED_FOR_REVIEW")
        self.assertFalse((self.checkout / "docs" / "demo.md").exists())

    def test_replay_blocked(self):
        self.run_pipeline()
        with self.assertRaises(ReplayBlocked):
            self.run_pipeline()

    def test_wrong_approved_digest_blocked(self):
        expected = dict(self.expected, task_digest="f" * 64)
        with self.assertRaises(ValueError):
            self.run_pipeline(expected=expected)
        self.assertFalse(self.ledger_path.exists())

    def test_no_approval_blocked(self):
        expected = dict(self.expected, execution_authorized=False)
        with self.assertRaises(ValueError):
            self.run_pipeline(expected=expected)
        self.assertFalse(self.ledger_path.exists())

    def test_unappliable_patch_blocked_without_reservation(self):
        (self.checkout / "docs" / "demo.md").write_text("already exists")
        with self.assertRaisesRegex(ReviewRejected, "git_apply_check_failed"):
            self.run_pipeline()
        self.assertFalse(self.ledger_path.exists())

    def test_bad_patch_contents_blocked(self):
        patch = self.patch.replace(b"+++ b/docs/demo.md", b"+++ b/docs/other.md")
        receipt = dict(self.receipt, artifact_sha256=hashlib.sha256(patch).hexdigest())
        expected = dict(self.expected, artifact_sha256=receipt["artifact_sha256"])
        with self.assertRaises(ValueError):
            self.run_pipeline(patch=patch, receipt=receipt, expected=expected)
        self.assertFalse(self.ledger_path.exists())

    def test_wrong_artifact_id_blocked(self):
        receipt = dict(self.receipt, artifact_id=457)
        with self.assertRaises(ValueError):
            self.run_pipeline(receipt=receipt)
        self.assertFalse(self.ledger_path.exists())

    def test_expired_blocked(self):
        receipt = dict(self.receipt, expired=True)
        expected = dict(self.expected, expired=True)
        with self.assertRaises(ValueError):
            self.run_pipeline(receipt=receipt, expected=expected)
        self.assertFalse(self.ledger_path.exists())

    def test_does_not_execute_generated_code(self):
        self.run_pipeline()
        self.assertFalse((self.checkout / "docs" / "demo.md").exists())

if __name__ == "__main__":
    unittest.main()
