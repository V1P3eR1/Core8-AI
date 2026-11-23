"""Regression tests for private artifact leakage paths and file permissions."""
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

from private_storage import (PrivateStorageError, private_directory,
                             safe_read_private_json, exclusive_private_write)


class PrivateStorageTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.path = Path(self.root.name)
        self.vault = self.path / "owner-vault"
        self.vault.mkdir(mode=0o700)
        os.chmod(self.vault, 0o700)

    def test_owner_only_exclusive_write(self):
        target = self.vault / "dashboard.html"
        self.assertEqual(exclusive_private_write(target, "<p>private</p>"), target)
        self.assertEqual(target.read_text(encoding="utf-8"), "<p>private</p>")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        with self.assertRaisesRegex(PrivateStorageError, "already_exists"):
            exclusive_private_write(target, "overwritten")
        self.assertEqual(target.read_text(), "<p>private</p>")

    def test_world_readable_directory_refused(self):
        os.chmod(self.vault, 0o755)
        with self.assertRaisesRegex(PrivateStorageError, "permissions"):
            exclusive_private_write(self.vault / "out.html", "secret")

    def test_git_repository_directory_refused(self):
        (self.path / ".git").mkdir()
        with self.assertRaisesRegex(PrivateStorageError, "git_checkout"):
            exclusive_private_write(self.vault / "out.html", "secret")

    def test_symlink_in_directory_chain_refused(self):
        alias = self.path / "alias"
        alias.symlink_to(self.vault, target_is_directory=True)
        with self.assertRaisesRegex(PrivateStorageError, "symlink"):
            exclusive_private_write(alias / "out.html", "secret")

    def test_absolute_path_and_extension_required(self):
        for path in (Path("out.html"), self.vault / "out.json"):
            with self.assertRaises(PrivateStorageError):
                exclusive_private_write(path, "secret")

    def test_existing_symlink_file_is_never_followed(self):
        real = self.vault / "real.html"
        real.write_text("keep")
        alias = self.vault / "out.html"
        alias.symlink_to(real)
        with self.assertRaises(PrivateStorageError):
            exclusive_private_write(alias, "leak")
        self.assertEqual(real.read_text(), "keep")

    def test_private_input_read_and_bad_input_disallowed(self):
        src = self.vault / "summary.json"
        src.write_text(json.dumps({"count": 9}), encoding="utf-8")
        self.assertEqual(safe_read_private_json(src, 500, require_private=True),
                         {"count": 9})
        with self.assertRaises(PrivateStorageError):
            safe_read_private_json(src, 2, require_private=True)
        link = self.vault / "link.json"
        link.symlink_to(src)
        with self.assertRaises(PrivateStorageError):
            safe_read_private_json(link, 500, require_private=True)

    def test_symlink_of_git_parent_cannot_escape(self):
        repo = self.path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        child = repo / "private"
        child.mkdir(mode=0o700)
        os.chmod(child, 0o700)
        with self.assertRaises(PrivateStorageError):
            private_directory(child)


if __name__ == "__main__":
    unittest.main()
