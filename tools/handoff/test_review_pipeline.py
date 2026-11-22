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
        (self.checkout / "docs" / "existing.md").write_text("fixture\n")
        subprocess.run(["git", "-C", str(self.checkout), "add",
                        "docs/existing.md"], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "-c", "user.name=Core8 Test",
                        "-c", "user.email=core8-test@example.invalid",
                        "commit", "-qm", "initial fixture"], check=True)
        self.base_sha = subprocess.check_output(
            ["git", "-C", str(self.checkout), "rev-parse", "HEAD"], text=True).strip()
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
                             execution_authorized=True, checkout_sha=self.base_sha)
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
        with self.assertRaisesRegex(ReviewRejected, "checkout_not_clean"):
            self.run_pipeline()
        self.assertFalse(self.ledger_path.exists())

    def test_untracked_file_blocks_without_reserving(self):
        (self.checkout / "docs" / "untracked.txt").write_text("unexpected")
        with self.assertRaisesRegex(ReviewRejected, "checkout_not_clean"):
            self.run_pipeline()
        self.assertFalse(self.ledger_path.exists())

    def test_ignored_file_blocks_without_reserving(self):
        (self.checkout / ".gitignore").write_text("ignored-runtime.txt\n")
        subprocess.run(["git", "-C", str(self.checkout), "add", ".gitignore"],
                       check=True)
        subprocess.run(["git", "-C", str(self.checkout), "-c", "user.name=Core8 Test",
                        "-c", "user.email=core8-test@example.invalid",
                        "commit", "-qm", "Add ignore fixture"], check=True)
        self.base_sha = subprocess.check_output(
            ["git", "-C", str(self.checkout), "rev-parse", "HEAD"], text=True).strip()
        self.expected["checkout_sha"] = self.base_sha
        (self.checkout / "ignored-runtime.txt").write_text("untrusted")
        with self.assertRaisesRegex(ReviewRejected, "checkout_not_clean"):
            self.run_pipeline()
        self.assertFalse(self.ledger_path.exists())

    def test_subdirectory_is_not_a_checkout_root(self):
        directory = self.checkout / "docs"
        with self.assertRaisesRegex(ReviewRejected, "checkout_not_git_root"):
            stage_review(
                receipt=self.receipt, expected_record=self.expected,
                patch_bytes=self.patch, now=self.now,
                ledger_path=self.ledger_path, checkout_path=directory)
        self.assertFalse(self.ledger_path.exists())

    def test_tracked_modification_blocks_without_reserving(self):
        (self.checkout / "docs" / "existing.md").write_text("modified")
        with self.assertRaisesRegex(ReviewRejected, "checkout_not_clean"):
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

    def test_untrusted_checkout_sha_blocked(self):
        expected = dict(self.expected, checkout_sha="f" * 40)
        with self.assertRaisesRegex(ReviewRejected, "checkout_sha_mismatch"):
            self.run_pipeline(expected=expected)
        self.assertFalse(self.ledger_path.exists())

    def test_missing_checkout_sha_blocked(self):
        expected = dict(self.expected)
        del expected["checkout_sha"]
        with self.assertRaisesRegex(ReviewRejected, "missing_trusted_checkout_sha"):
            self.run_pipeline(expected=expected)
        self.assertFalse(self.ledger_path.exists())

if __name__ == "__main__":
    unittest.main()
