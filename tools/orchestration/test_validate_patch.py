import unittest
from validate_patch import validate_patch, Rejected, allowed_path

GOOD = b"""diff --git a/docs/example.md b/docs/example.md
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/docs/example.md
@@ -0,0 +1,1 @@
+Safe synthetic document
"""

def changed(before, after):
    return GOOD.replace(before, after)

class PatchAdmissionTests(unittest.TestCase):
    def test_synthetic_safe_markdown_is_structurally_admitted_but_not_executable(self):
        r = validate_patch(GOOD)
        self.assertEqual(r["paths"], ["docs/example.md"])
        self.assertFalse(r["is_approved_for_execution"])

    def test_blocks_workflows_deploy_env_executables_and_traversal(self):
        for path in (".github/workflows/evil.yml", "apps/x/deploy/install.sh",
                     "apps/x/.env", "docs/../../.github/workflows/a.yml",
                     "docs/secret.key", "/docs/test.md", "docs\\bad.md"):
            self.assertFalse(allowed_path(path), path)

    def test_rejects_untrusted_path(self):
        with self.assertRaises(Rejected):
            validate_patch(changed(b"docs/example.md", b"../.github/workflows/evil.yml"))

    def test_rejects_symlink_and_executable_modes(self):
        for old, new in [
            (b"new file mode 100644", b"new file mode 120000"),
            (b"new file mode 100644", b"new file mode 100755"),
            (b"new file mode 100644", b"new file mode 160000"),
        ]:
            with self.assertRaises(Rejected):
                validate_patch(changed(old, new))

    def test_rejects_rename_and_binary(self):
        with self.assertRaises(Rejected):
            validate_patch(GOOD + b"rename from docs/old.md\n")
        with self.assertRaises(Rejected):
            validate_patch(GOOD + b"GIT binary patch\n")

    def test_rejects_embedded_secret(self):
        with self.assertRaises(Rejected):
            validate_patch(GOOD + b"+sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567\n")

    def test_rejects_oversized_artifact(self):
        with self.assertRaises(Rejected):
            validate_patch(GOOD + b"x" * 160001)

    def test_rejects_duplicate_diff(self):
        with self.assertRaises(Rejected):
            validate_patch(GOOD + GOOD)

    def test_rejects_blank_artifact(self):
        with self.assertRaises(Rejected):
            validate_patch(b"")

    def test_rejects_header_mismatch(self):
        with self.assertRaises(Rejected):
            validate_patch(changed(b"+++ b/docs/example.md", b"+++ b/docs/other.md"))

if __name__ == "__main__":
    unittest.main()
