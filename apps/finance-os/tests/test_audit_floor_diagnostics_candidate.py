"""Offline regression tests for read-only audit floor diagnostics."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_floor_diagnostics_candidate import diagnose_audit_keyring
from external_floor_candidate import IndependentGenerationFloor
from tenant_access import FinanceAccessDenied


class ScriptedFloor(IndependentGenerationFloor):
    def __init__(self, values):
        self.values = iter(values)
        self.reads = []

    def read(self, namespace):
        self.reads.append(namespace)
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return value

    def compare_and_advance(self, *args):
        raise AssertionError("diagnostics must not advance floor")


class AuditFloorDiagnosticsTests(unittest.TestCase):
    def diagnose(self, values):
        floor = ScriptedFloor(values)
        conn = Mock()
        conn.execute.return_value.fetchone.return_value = (1,)
        with patch("audit_floor_diagnostics_candidate.recover_audit_keyring_store") as recover:
            try:
                return diagnose_audit_keyring(
                    conn, floor=floor, namespace="ci_audit",
                    signing_key=b"synthetic", trusted_key_material={},
                )
            finally:
                self.assertEqual(floor.reads, ["ci_audit", "ci_audit"])
                conn.execute.assert_called_once()
                recover.assert_called_once()

    def test_stable_floor_is_healthy(self):
        self.assertEqual(self.diagnose([1, 1]).status, "healthy")

    def test_concurrent_advance_is_indeterminate(self):
        result = self.diagnose([1, 2])
        self.assertEqual((result.status, result.floor_generation,
                          result.database_generation), ("indeterminate", 2, 1))

    def test_second_read_failure_or_invalid_value_denies(self):
        for value in (TimeoutError("synthetic outage"), None, True, 0, "1"):
            with self.subTest(value=value), self.assertRaises(FinanceAccessDenied):
                self.diagnose([1, value])


if __name__ == "__main__":
    unittest.main()
