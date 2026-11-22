"""Synthetic full read-only artifact -> review pipeline integration evidence.

No external network, no real approvals, no Claude API, no GitHub PR writes.
"""
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from artifact_unpack import UnsafeArtifact, extract_verified_patch
from github_provenance import (ARTIFACT_NAME, REPO, REPO_ID, WORKFLOW_PATH,
                               GitHubReadOnly)
from replay_ledger import ReplayBlocked
from review_pipeline import stage_review

PATCH = (b"diff --git a/docs/demo.md b/docs/demo.md\n"
         b"new file mode 100644\n"
         b"index 0000000..1234567\n"
         b"--- /dev/null\n"
         b"+++ b/docs/demo.md\n"
         b"@@ -0,0 +1 @@\n"
         b"+hello\n")


class FakeResponse:
    def __init__(self, value):
        self.bytes = io.BytesIO(json.dumps(value).encode())
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def read(self, size=-1): return self.bytes.read(size)


class FakeGitHub:
    def __init__(self, run, artifact):
        self.run, self.artifact = run, artifact
    def open(self, request, timeout):
        if request.full_url.endswith("/actions/runs/123"):
            return FakeResponse(self.run)
        if request.full_url.endswith("/actions/artifacts/456"):
            return FakeResponse(self.artifact)
        raise AssertionError("unplanned API access")


class EndToEndSyntheticTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.checkout = self.root / "repo"
        self.checkout.mkdir()
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
        (self.checkout / "docs").mkdir()
        subprocess.run(["git", "-C", str(self.checkout), "-c", "user.name=Fixture",
                        "-c", "user.email=fixture@example.invalid",
                        "commit", "--allow-empty", "-qm", "initial"], check=True)
        self.base = subprocess.check_output(
            ["git", "-C", str(self.checkout), "rev-parse", "HEAD"],
            text=True).strip()
        self.ledger = self.root / "ledger.db"
        self.now = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("core8-implementation.patch", PATCH)
        self.archive = archive.getvalue()
        sha = hashlib.sha256(self.archive).hexdigest()
        self.run = dict(
            id=123, repository=dict(full_name=REPO, id=REPO_ID),
            event="issue_comment", head_branch="main", head_sha=self.base,
            path=WORKFLOW_PATH, status="completed", conclusion="success",
            run_attempt=1, actor={"id": 999}, triggering_actor={"id": 999})
        self.artifact = dict(
            id=456, name=ARTIFACT_NAME, expired=False, digest="sha256:" + sha,
            created_at="2026-11-22T10:00:00Z",
            expires_at="2026-11-29T10:00:00Z",
            workflow_run=dict(id=123, head_sha=self.base,
                              head_branch="main", repository_id=REPO_ID))

    def prepare(self, approved=True, archive=None):
        record = GitHubReadOnly(
            "synthetic-token", opener=FakeGitHub(self.run, self.artifact)
        ).fetch_verified(run_id=123, artifact_id=456, head_sha=self.base,
                         expected_actor_id=999)
        extracted = extract_verified_patch(
            self.archive if archive is None else archive,
            trusted_archive_sha256=record["archive_sha256"])
        receipt = {
            "repo": record["repo"], "run_id": record["run_id"],
            "artifact_id": record["artifact_id"], "head_sha": record["head_sha"],
            "task_digest": "b" * 64, "task_revision": 1,
            "issue_number": 62, "approver_id": record["approver_id"],
            "run_event": record["run_event"],
            "run_conclusion": record["run_conclusion"],
            "artifact_name": record["artifact_name"],
            "expired": record["expired"],
            "artifact_sha256": extracted["patch_sha256"],
            "created_at": record["created_at"], "expires_at": record["expires_at"],
        }
        # The synthetic approval here is ONLY a fixture. A production caller
        # must separately verify the real private Notion/GitHub human decision.
        expected = dict(receipt, decision="Approved" if approved else "Proposal",
                        public_export=True, execution_authorized=approved,
                        checkout_sha=self.base)
        return stage_review(
            receipt=receipt, expected_record=expected,
            patch_bytes=extracted["patch_bytes"], now=self.now,
            ledger_path=self.ledger, checkout_path=self.checkout)

    def test_valid_synthetic_chain_reserves_without_modifying_repo(self):
        result = self.prepare()
        self.assertEqual(result["status"], "RESERVED_FOR_REVIEW")
        self.assertFalse((self.checkout / "docs" / "demo.md").exists())

    def test_replay_stops_second_attempt(self):
        self.prepare()
        with self.assertRaises(ReplayBlocked): self.prepare()

    def test_unapproved_task_stops_before_reservation(self):
        with self.assertRaises(ValueError): self.prepare(approved=False)
        self.assertFalse(self.ledger.exists())

    def test_spoofed_run_actor_blocks_before_reservation(self):
        self.run["actor"]["id"] = 12345
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.ledger.exists())

    def test_spoofed_rerun_actor_blocks_before_reservation(self):
        self.run["triggering_actor"]["id"] = 12345
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.ledger.exists())

    def test_modified_archive_rejected_before_reservation(self):
        with self.assertRaises(UnsafeArtifact):
            self.prepare(archive=self.archive + b"tampering")
        self.assertFalse(self.ledger.exists())


if __name__ == "__main__":
    unittest.main()
