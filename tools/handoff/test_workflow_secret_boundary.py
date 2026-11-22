"""Static contract tests: the patch-packaging step must never receive AI keys.

These are source assertions only. A separate security review of generated-code
isolation, exact artifact provenance and authorization remains mandatory.
"""
from pathlib import Path
import unittest


WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "claude-issues.yml"


class SecretFreePackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")
        cls.pack = cls.source.split("      - name: Package changes without executing generated code\n", 1)[1].split(
            "      - uses: actions/upload-artifact@", 1)[0]

    def test_packaging_has_no_environment_secrets(self):
        self.assertNotIn("        env:\n", self.pack)
        self.assertNotIn("secrets.", self.pack)
        self.assertNotIn("ANTHROPIC_API_KEY", self.pack)
        self.assertNotIn("GITHUB_TOKEN", self.pack)
        self.assertNotIn("NOTION_TOKEN", self.pack)

    def test_patch_bounded_before_loading(self):
        self.assertIn("path.stat().st_size > 256 * 1024", self.pack)
        self.assertLess(self.pack.index("path.stat().st_size"), self.pack.index("path.read_text()"))

    def test_no_generated_code_execution(self):
        self.assertIn("git diff --binary -- apps docs", self.pack)
        for bad in ("docker run", "pytest ", "python -m ", "bash -c", "npm install"):
            self.assertNotIn(bad, self.pack)

    def test_secret_scanner_still_active(self):
        self.assertIn("PRIVATE KEY", self.pack)
        self.assertIn("github_pat_", self.pack)


if __name__ == "__main__":
    unittest.main()
