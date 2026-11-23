"""Disposable file-backed floor: restart, concurrent CAS, tenant isolation."""
import concurrent.futures
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlite_generation_floor_candidate import SQLiteGenerationFloorCandidate
from tenant_access import FinanceAccessDenied


class SQLiteFloorCandidateTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = str(Path(self.dir.name) / "floor.sqlite")
        self.floor = SQLiteGenerationFloorCandidate(path=self.path)
        self.floor.initialize_test_store()
        self.floor.provision_test_namespace("ci_alpha")
        self.floor.provision_test_namespace("ci_beta")

    def tearDown(self):
        self.dir.cleanup()

    def test_restart_and_namespace_isolation(self):
        self.assertTrue(self.floor.compare_and_advance("ci_alpha", 1, 2))
        reopened = SQLiteGenerationFloorCandidate(path=self.path)
        self.assertEqual(reopened.read("ci_alpha"), 2)
        self.assertEqual(reopened.read("ci_beta"), 1)
        self.assertFalse(reopened.compare_and_advance("ci_alpha", 1, 2))
        self.assertEqual(reopened.read("ci_alpha"), 2)

    def test_concurrent_writers_only_one_cas_commits(self):
        barrier = threading.Barrier(6)
        def attempt(_):
            contender = SQLiteGenerationFloorCandidate(path=self.path)
            barrier.wait(timeout=10)
            return contender.compare_and_advance("ci_alpha", 1, 2)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(attempt, range(6)))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 5)
        self.assertEqual(self.floor.read("ci_alpha"), 2)

    def test_invalid_input_and_no_implicit_provision(self):
        for ns in ("../other", "", "A", None):
            with self.subTest(ns=ns), self.assertRaises(FinanceAccessDenied):
                self.floor.read(ns)
        for expected, proposed in ((True, 2), (1, 3), (2, 2),
                                   (0, 1), (1, True)):
            with self.subTest(pair=(expected, proposed)):
                with self.assertRaises(FinanceAccessDenied):
                    self.floor.compare_and_advance("ci_alpha", expected, proposed)
        with self.assertRaises(FinanceAccessDenied):
            self.floor.read("ci_missing")
        with self.assertRaises(FinanceAccessDenied):
            self.floor.compare_and_advance("ci_missing", 1, 2)
        with self.assertRaises(FinanceAccessDenied):
            self.floor.provision_test_namespace("ci_alpha")

    def test_fail_closed_if_database_missing_or_corrupt(self):
        missing = SQLiteGenerationFloorCandidate(
            path=str(Path(self.dir.name) / "missing.sqlite")
        )
        with self.assertRaises(FinanceAccessDenied):
            missing.read("ci_alpha")
        with self.assertRaises(FinanceAccessDenied):
            missing.compare_and_advance("ci_alpha", 1, 2)
        self.assertEqual(self.floor.read("ci_alpha"), 1)
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TABLE floor_candidate")
        with self.assertRaises(FinanceAccessDenied):
            self.floor.read("ci_alpha")
        with self.assertRaises(FinanceAccessDenied):
            self.floor.compare_and_advance("ci_alpha", 1, 2)

    def test_full_file_restore_is_not_detected_without_external_anchor(self):
        import shutil
        backup = str(Path(self.dir.name) / "old-copy.sqlite")
        shutil.copy2(self.path, backup)
        self.assertTrue(self.floor.compare_and_advance("ci_alpha", 1, 2))
        shutil.copy2(backup, self.path)
        # Explicitly document missing tamper resistance: do not mistake
        # separate-file persistence for a trusted remote/monotonic floor.
        self.assertEqual(self.floor.read("ci_alpha"), 1)


if __name__ == "__main__":
    unittest.main()
