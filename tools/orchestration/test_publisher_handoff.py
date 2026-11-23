import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from stage_patch import StageRejected, stage
from draft_publisher import inspect_bundle, publish
from test_draft_publisher import FakeApi

SCOPE = "a" * 64


def git(folder, *args):
    return subprocess.check_output(["git", "-C", str(folder), *args]).decode().strip()


class StageToPublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "source"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "old.md").write_text("original\n")
        git(self.repo, "add", "--all")
        git(self.repo, "-c", "user.name=Test", "-c", "user.email=test@invalid.local",
            "commit", "-qm", "fixture")
        self.base = git(self.repo, "rev-parse", "HEAD")
        self.patch = (b"diff --git a/docs/new.md b/docs/new.md\n"
                      b"new file mode 100644\nindex 0000000..ce01362\n"
                      b"--- /dev/null\n+++ b/docs/new.md\n@@ -0,0 +1 @@\n+hello\n")
        self.artifact = hashlib.sha256(self.patch).hexdigest()
        self.output = self.root / "bundle.json"

    def build(self):
        return stage(self.repo, self.patch, self.artifact, self.base, SCOPE, bundle_output=self.output)

    def test_staged_bundle_matches_writer_and_dry_run(self):
        manifest = self.build()
        raw = self.output.read_bytes()
        self.assertEqual(manifest["bundle_sha256"], hashlib.sha256(raw).hexdigest())
        idem, files = inspect_bundle(raw, manifest["bundle_sha256"], base_sha=self.base,
                                     scope_sha=SCOPE, artifact_sha=self.artifact)
        self.assertEqual(files[0][0], "docs/new.md")
        self.assertEqual(idem, manifest["idempotency_key"])
        api = FakeApi(main_sha=self.base)
        api.repo = "owner/repo"
        result = publish(api, repo="owner/repo", base_sha=self.base, bundle_raw=raw,
                         bundle_hash=manifest["bundle_sha256"], scope_sha=SCOPE,
                         artifact_sha=self.artifact)
        self.assertEqual(result["status"], "CREATED_DRAFT")
        self.assertFalse((self.repo / "docs" / "new.md").exists())

    def test_replay_does_not_overwrite_bundle(self):
        self.build()
        with self.assertRaises(FileExistsError):
            self.build()

    def test_refuses_output_into_source_checkout(self):
        with self.assertRaisesRegex(StageRejected, "bundle_must_be_outside_source"):
            stage(self.repo, self.patch, self.artifact, self.base, SCOPE,
                  bundle_output=self.repo / "docs" / "bundle.json")

    def test_wrong_artifact_never_creates_bundle(self):
        with self.assertRaisesRegex(StageRejected, "artifact_hash_mismatch"):
            stage(self.repo, self.patch, "0" * 64, self.base, SCOPE,
                  bundle_output=self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
