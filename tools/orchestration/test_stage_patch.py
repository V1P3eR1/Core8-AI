import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from stage_patch import StageRejected, stage


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args]).decode().strip()


class StagePatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q")
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "existing.md").write_text("original\n")
        git(self.repo, "add", "--all")
        git(self.repo, "-c", "user.name=Test", "-c", "user.email=test@invalid.local",
            "commit", "-qm", "fixture")
        self.base = git(self.repo, "rev-parse", "HEAD")

    def patch(self, path="docs/new.md", payload="hello"):
        return (f"diff --git a/{path} b/{path}\nnew file mode 100644\n"
                f"index 0000000..ce01362\n--- /dev/null\n+++ b/{path}\n"
                f"@@ -0,0 +1 @@\n+{payload}\n").encode()

    def apply(self, patch, base=None, scope="a" * 64, digest=None):
        return stage(self.repo, patch, digest or hashlib.sha256(patch).hexdigest(),
                     base or self.base, scope)

    def test_git_subprocess_does_not_inherit_api_credentials(self):
        import os
        from unittest import mock
        import stage_patch
        real_run = subprocess.run
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-only-secret",
                                          "NOTION_TOKEN": "test-only-secret",
                                          "GIT_CONFIG_GLOBAL": "/tmp/host-config"}):
            with mock.patch("stage_patch.subprocess.run", wraps=real_run) as call:
                self.assertEqual(stage_patch.git(self.repo, "rev-parse", "HEAD").decode().strip(), self.base)
                environment = call.call_args.kwargs["env"]
        self.assertNotIn("ANTHROPIC_API_KEY", environment)
        self.assertNotIn("NOTION_TOKEN", environment)
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], "/dev/null")
        self.assertEqual(environment["HOME"], "/nonexistent")

    def test_valid_stage_is_read_only(self):
        result = self.apply(self.patch())
        self.assertEqual(result["paths"], ["docs/new.md"])
        self.assertEqual(result["status"], "REVIEW_ONLY")
        self.assertFalse((self.repo / "docs" / "new.md").exists())

    def test_replay_idempotency(self):
        one = self.apply(self.patch())
        self.assertEqual(one["idempotency_key"], self.apply(self.patch())["idempotency_key"])
        different = self.apply(self.patch(), scope="b" * 64)
        self.assertNotEqual(one["idempotency_key"], different["idempotency_key"])

    def test_bad_artifact_digest(self):
        with self.assertRaisesRegex(StageRejected, "artifact_hash_mismatch"):
            self.apply(self.patch(), digest="0" * 64)

    def test_bad_scope_digest(self):
        with self.assertRaisesRegex(StageRejected, "invalid_trusted_metadata"):
            self.apply(self.patch(), scope="not-a-digest")

    def test_wrong_base_commit(self):
        with self.assertRaisesRegex(StageRejected, "base_sha_mismatch"):
            self.apply(self.patch(), base="b" * 40)

    def test_modified_source(self):
        (self.repo / "docs" / "existing.md").write_text("modified\n")
        with self.assertRaisesRegex(StageRejected, "dirty_source"):
            self.apply(self.patch())

    def test_untracked_source(self):
        (self.repo / "docs" / "untracked.txt").write_text("new")
        with self.assertRaisesRegex(StageRejected, "dirty_source"):
            self.apply(self.patch())

    def test_ignored_source_is_rejected(self):
        (self.repo / ".gitignore").write_text("ignored-secret.txt\n")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "-c", "user.name=Test", "-c",
            "user.email=test@invalid.local", "commit", "-qm", "ignore fixture")
        self.base = git(self.repo, "rev-parse", "HEAD")
        (self.repo / "ignored-secret.txt").write_text("hidden data")
        with self.assertRaisesRegex(StageRejected, "dirty_source"):
            self.apply(self.patch())

    def test_nested_checkout_is_not_worktree_root(self):
        nested = self.repo / "docs"
        patch = self.patch()
        with self.assertRaisesRegex(StageRejected, "not_a_git_checkout"):
            stage(nested, patch, hashlib.sha256(patch).hexdigest(),
                  self.base, "a" * 64)

    def test_local_fsmonitor_helper_is_not_executed(self):
        helper = self.repo.parent / "fsmonitor-helper.sh"
        marker = self.repo.parent / "helper-executed"
        helper.write_text("#!/bin/sh\ntouch '" + str(marker) + "'\nexit 0\n")
        helper.chmod(0o755)
        git(self.repo, "config", "core.fsmonitor", str(helper))
        self.apply(self.patch())
        self.assertFalse(marker.exists())

    def test_reject_workflow_path(self):
        with self.assertRaisesRegex(StageRejected, "patch_"):
            self.apply(self.patch(path=".github/workflows/exploit.yml"))

    def test_reject_traversal(self):
        with self.assertRaisesRegex(StageRejected, "patch_"):
            self.apply(self.patch(path="docs/../bad.md"))

    def test_reject_symlink(self):
        patch = self.patch().replace(b"new file mode 100644", b"new file mode 120000")
        with self.assertRaisesRegex(StageRejected, "patch_nonregular_mode"):
            self.apply(patch)

    def test_reject_secret(self):
        with self.assertRaisesRegex(StageRejected, "possible_secret"):
            self.apply(self.patch(payload="sk-ant-" + "X" * 30))

    def test_reject_bad_hunk(self):
        patch = self.patch().replace(b"@@ -0,0 +1 @@", b"@@ -0,1 +1 @@")
        with self.assertRaisesRegex(StageRejected, "patch_truncated_hunk"):
            self.apply(patch)

    def test_reject_overwrite(self):
        with self.assertRaisesRegex(StageRejected, "git_apply_failed"):
            self.apply(self.patch(path="docs/existing.md"))

    def test_modify_existing_file(self):
        patch = (b"diff --git a/docs/existing.md b/docs/existing.md\n"
                 b"index 4b48c16..ce01362 100644\n--- a/docs/existing.md\n"
                 b"+++ b/docs/existing.md\n@@ -1 +1 @@\n-original\n+updated\n")
        self.assertEqual(self.apply(patch)["paths"], ["docs/existing.md"])

    def test_reject_invalid_repository(self):
        other = self.repo / "empty"
        other.mkdir()
        with self.assertRaisesRegex(StageRejected, "not_a_git_checkout"):
            stage(other, self.patch(), hashlib.sha256(self.patch()).hexdigest(), self.base, "a" * 64)


if __name__ == "__main__":
    unittest.main()
