"""Offline, disposable-repository regression tests. Never connects to or mutates a VPS."""
import os
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "release-preflight.sh"


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


class ReleasePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = pathlib.Path(self.temp.name)
        self.remote = base / "origin.git"
        self.checkout = base / "checkout"
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        subprocess.run(["git", "init", "-b", "main", str(self.checkout)], check=True, capture_output=True)
        git(self.checkout, "config", "user.email", "test@example.invalid")
        git(self.checkout, "config", "user.name", "Test Runner")
        (self.checkout / "README").write_text("fixture\n")
        git(self.checkout, "add", "README")
        git(self.checkout, "commit", "-m", "Fixture")
        self.sha = git(self.checkout, "rev-parse", "HEAD")
        git(self.checkout, "remote", "add", "origin", str(self.remote))
        git(self.checkout, "push", "-u", "origin", "main")
        git(self.checkout, "fetch", "origin", "main")

    def preflight(self, sha=None):
        env = dict(os.environ, ROOT=str(self.checkout))
        env.pop("RELEASE_SHA", None)
        if sha is not None:
            env["RELEASE_SHA"] = sha
        return subprocess.run(["bash", str(SCRIPT)], env=env, text=True, capture_output=True)

    def test_missing_sha_fails_closed(self):
        self.assertNotEqual(self.preflight().returncode, 0)

    def test_short_sha_fails_closed(self):
        self.assertNotEqual(self.preflight(self.sha[:8]).returncode, 0)

    def test_unknown_sha_fails_closed(self):
        self.assertNotEqual(self.preflight("f" * 40).returncode, 0)

    def test_valid_main_commit_is_preflight_only(self):
        result = self.preflight(self.sha)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PRECHECK_ONLY=PASS", result.stdout)
        self.assertEqual(git(self.checkout, "rev-parse", "HEAD"), self.sha)

    def test_dirty_worktree_fails_closed(self):
        (self.checkout / "README").write_text("modified\n")
        self.assertNotEqual(self.preflight(self.sha).returncode, 0)

    def test_untracked_build_input_fails_closed(self):
        (self.checkout / "unexpected-build-context").write_text("unreviewed\\n")
        result = self.preflight(self.sha)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("untracked", result.stderr)

    def test_ignored_runtime_file_does_not_break_preflight(self):
        # A deliberately ignored secret/config file is not read or echoed.
        (self.checkout / ".gitignore").write_text(".env.production\\n")
        git(self.checkout, "add", ".gitignore")
        git(self.checkout, "commit", "-m", "Ignore runtime config")
        self.sha = git(self.checkout, "rev-parse", "HEAD")
        git(self.checkout, "push", "origin", "main")
        git(self.checkout, "fetch", "origin", "main")
        (self.checkout / ".env.production").write_text("FAKE_TEST_VALUE=redacted\\n")
        result = self.preflight(self.sha)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("FAKE_TEST_VALUE", result.stdout)

    def test_unmerged_commit_fails_closed(self):
        git(self.checkout, "checkout", "-b", "feature")
        (self.checkout / "README").write_text("feature\n")
        git(self.checkout, "commit", "-am", "Unmerged")
        unmerged = git(self.checkout, "rev-parse", "HEAD")
        self.assertNotEqual(self.preflight(unmerged).returncode, 0)


if __name__ == "__main__":
    unittest.main()
