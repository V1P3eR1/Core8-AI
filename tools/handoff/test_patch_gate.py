import hashlib
import unittest

from patch_gate import RejectedPatch, validate_patch


def make_patch(path="docs/demo.md", extra="", content="hello"):
    return (f"diff --git a/{path} b/{path}\nnew file mode 100644\n"
            f"index 0000000..1234567\n--- /dev/null\n+++ b/{path}\n"
            f"@@ -0,0 +1 @@\n+{content}\n{extra}").encode()


def verify(payload):
    return validate_patch(payload, hashlib.sha256(payload).hexdigest())


class PatchGateTests(unittest.TestCase):
    def test_valid_docs(self):
        self.assertEqual(verify(make_patch())["files"], ["docs/demo.md"])

    def test_valid_apps(self):
        self.assertEqual(verify(make_patch("apps/demo/file.py"))["files"], ["apps/demo/file.py"])

    def test_no_files(self):
        with self.assertRaises(RejectedPatch): verify(b"nothing here")

    def test_bad_digest(self):
        with self.assertRaisesRegex(RejectedPatch, "digest_mismatch"):
            validate_patch(make_patch(), "0" * 64)

    def test_invalid_digest(self):
        with self.assertRaisesRegex(RejectedPatch, "invalid_digest"):
            validate_patch(make_patch(), "invalid")

    def test_blocked_paths(self):
        for path in [".github/workflows/x.yml", "README.md", "docs/../x",
                     "apps//x", "docs/.env", "apps/svc/secret.key",
                     "docs/.git/config", "docs/secrets/key", "apps\\folder\\x"]:
            with self.subTest(path=path), self.assertRaises(RejectedPatch):
                verify(make_patch(path))

    def test_renames(self):
        with self.assertRaisesRegex(RejectedPatch, "rename_copy_or_submodule"):
            verify(make_patch(extra="rename from docs/demo.md\n"))
        with self.assertRaisesRegex(RejectedPatch, "rename_not_allowed"):
            verify(make_patch().replace(
                b"diff --git a/docs/demo.md b/docs/demo.md",
                b"diff --git a/docs/demo.md b/docs/new.md"))

    def test_symlink(self):
        with self.assertRaisesRegex(RejectedPatch, "nonregular_mode"):
            verify(make_patch().replace(b"new file mode 100644", b"new file mode 120000"))

    def test_secret(self):
        with self.assertRaisesRegex(RejectedPatch, "possible_secret"):
            verify(make_patch(content="sk-ant-" + "A" * 30))

    def test_binary(self):
        with self.assertRaisesRegex(RejectedPatch, "binary_patch"):
            verify(make_patch() + b"GIT binary patch\n")

    def test_too_big(self):
        with self.assertRaisesRegex(RejectedPatch, "empty_or_oversize"):
            verify(make_patch(content="x" * 300000))

    def test_duplicates(self):
        with self.assertRaisesRegex(RejectedPatch, "duplicate_file"):
            verify(make_patch() + make_patch())

    def test_bad_hunk(self):
        with self.assertRaisesRegex(RejectedPatch, "missing_diff_hunks"):
            verify(make_patch().replace(b"@@ -0,0 +1 @@", b"not a hunk"))


if __name__ == "__main__":
    unittest.main()
