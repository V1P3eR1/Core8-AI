"""Protect open owner decisions against accidental assumptions or silent completion."""
import re
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "OWNER_INPUTS.md"

class OwnerTBDRegisterTests(unittest.TestCase):
    def test_register_contains_tbd_for_each_owner_field(self):
        doc = DOC.read_text(encoding="utf-8")
        section = doc.split("## TBD — Lev or accountant must decide", 1)[1].split("\n## ", 1)[0]
        rows = [r for r in section.splitlines() if r.startswith("| ") and not r.startswith("| Field") and not r.startswith("|---")]
        self.assertGreaterEqual(len(rows), 12)
        for row in rows:
            with self.subTest(row=row[:65]):
                cells = [part.strip() for part in row.strip("|").split("|")]
                self.assertGreaterEqual(len(cells), 5)
                self.assertIn("TBD", cells[1])
    def test_sensitive_values_not_embedded(self):
        text = DOC.read_text(encoding="utf-8")
        patterns = (
            r"(?i)sk_live_[a-zA-Z0-9]{12,}",
            r"(?i)rk_live_[a-zA-Z0-9]{12,}",
            r"(?i)whsec_[a-zA-Z0-9]{12,}",
            r"(?i)(?:api[_ -]?key|password)\s*[:=]\s*[A-Za-z0-9_-]{16,}",
        )
        for pattern in patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, text))

if __name__ == "__main__":
    unittest.main()
