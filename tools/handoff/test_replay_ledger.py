import tempfile
import threading
import unittest
from pathlib import Path
from replay_ledger import ReplayBlocked, ReplayLedger


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "ledger.sqlite3"
        self.ledger = ReplayLedger(self.path)
        self.args = dict(repo="V1P3eR1/Core8-AI", run_id=123, artifact_id=456,
                         task_digest="a" * 64, patch_sha256="b" * 64)

    def test_empty(self):
        self.assertIsNone(self.ledger.state(repo=self.args["repo"], run_id=123, artifact_id=456))

    def test_reservation(self):
        self.ledger.reserve(**self.args)
        self.assertEqual(self.ledger.state(repo=self.args["repo"], run_id=123, artifact_id=456), "RESERVED")

    def test_duplicate_blocked(self):
        self.ledger.reserve(**self.args)
        with self.assertRaisesRegex(ReplayBlocked, "already_reserved"):
            self.ledger.reserve(**self.args)

    def test_duplicate_other_hash_blocked(self):
        self.ledger.reserve(**self.args)
        with self.assertRaises(ReplayBlocked):
            self.ledger.reserve(**{**self.args, "patch_sha256": "c" * 64})

    def test_consumed(self):
        self.ledger.reserve(**self.args)
        self.ledger.mark_consumed(**self.args)
        self.assertEqual(self.ledger.state(repo=self.args["repo"], run_id=123, artifact_id=456), "CONSUMED")

    def test_double_consumption_blocked(self):
        self.ledger.reserve(**self.args)
        self.ledger.mark_consumed(**self.args)
        with self.assertRaises(ReplayBlocked):
            self.ledger.mark_consumed(**self.args)

    def test_consume_without_reservation(self):
        with self.assertRaises(ReplayBlocked):
            self.ledger.mark_consumed(**self.args)

    def test_wrong_hash_consume(self):
        self.ledger.reserve(**self.args)
        with self.assertRaises(ReplayBlocked):
            self.ledger.mark_consumed(**{**self.args, "task_digest": "0" * 64})
        self.assertEqual(self.ledger.state(repo=self.args["repo"], run_id=123, artifact_id=456), "RESERVED")

    def test_persistence_across_reopen(self):
        self.ledger.reserve(**self.args)
        again = ReplayLedger(self.path)
        with self.assertRaises(ReplayBlocked):
            again.reserve(**self.args)

    def test_distinct_artifacts_allowed(self):
        self.ledger.reserve(**self.args)
        self.ledger.reserve(**{**self.args, "artifact_id": 457})

    def test_bad_digest(self):
        with self.assertRaises(ReplayBlocked):
            self.ledger.reserve(**{**self.args, "task_digest": "invalid"})

    def test_zero_and_boolean_id(self):
        for value in (0, True, -1):
            with self.subTest(value=value), self.assertRaises(ReplayBlocked):
                self.ledger.reserve(**{**self.args, "run_id": value})

    def test_ephemeral_memory_blocked(self):
        with self.assertRaises(ReplayBlocked):
            ReplayLedger(":memory:")

    def test_parallel_reservation_exactly_one_wins(self):
        outcomes = []
        lock = threading.Lock()
        def worker():
            try:
                ReplayLedger(self.path).reserve(**self.args)
                value = "reserved"
            except ReplayBlocked:
                value = "blocked"
            with lock:
                outcomes.append(value)
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(outcomes.count("reserved"), 1)
        self.assertEqual(outcomes.count("blocked"), 7)


if __name__ == "__main__":
    unittest.main()
