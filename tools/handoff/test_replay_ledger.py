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

    def test_other_artifact_same_task_revision_blocked(self):
        self.ledger.reserve(**self.args)
        with self.assertRaisesRegex(ReplayBlocked, "already_reserved"):
            self.ledger.reserve(**{**self.args, "artifact_id": 457})

    def test_other_run_same_task_revision_blocked(self):
        self.ledger.reserve(**self.args)
        with self.assertRaisesRegex(ReplayBlocked, "already_reserved"):
            self.ledger.reserve(**{**self.args, "run_id": 124, "artifact_id": 457})

    def test_new_task_digest_allows_distinct_artifact(self):
        self.ledger.reserve(**self.args)
        self.ledger.reserve(**{**self.args, "run_id": 124, "artifact_id": 457,
                                "task_digest": "c" * 64})

    def test_migration_blocks_preexisting_duplicate_task(self):
        import sqlite3
        # Emulate two historical reservations made before the unique index.
        self.ledger.reserve(**self.args)
        with sqlite3.connect(self.path) as db:
            db.execute("DROP INDEX reservations_one_task")
            db.execute("INSERT INTO reservations VALUES (?, ?, ?, ?, ?, 'RESERVED')",
                       (self.args["repo"], 222, 333, self.args["task_digest"],
                        "c" * 64))
        with self.assertRaisesRegex(ReplayBlocked,
                                    "ambiguous_existing_task_reservations"):
            ReplayLedger(self.path)

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

    def test_symlink_ledger_path_rejected(self):
        redirected = Path(self.tmp.name) / "redirected.sqlite3"
        redirected.symlink_to(self.path)
        with self.assertRaisesRegex(ReplayBlocked, "persistent_storage_required"):
            ReplayLedger(redirected)

    def test_concurrent_distinct_artifacts_same_task_only_one_wins(self):
        outcomes = []
        lock = threading.Lock()

        def worker(i):
            args = {**self.args, "run_id": 1000 + i, "artifact_id": 2000 + i}
            try:
                ReplayLedger(self.path).reserve(**args)
                outcome = "reserved"
            except ReplayBlocked:
                outcome = "blocked"
            with lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(outcomes.count("reserved"), 1)
        self.assertEqual(outcomes.count("blocked"), 7)

    def test_failed_migration_preserves_historical_rows(self):
        import sqlite3
        self.ledger.reserve(**self.args)
        with sqlite3.connect(self.path) as db:
            db.execute("DROP INDEX reservations_one_task")
            db.execute("INSERT INTO reservations VALUES (?, ?, ?, ?, ?, 'RESERVED')",
                       (self.args["repo"], 444, 555, self.args["task_digest"],
                        "d" * 64))
        with self.assertRaisesRegex(ReplayBlocked, "ambiguous_existing_task_reservations"):
            ReplayLedger(self.path)
        with sqlite3.connect(self.path) as db:
            count = db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        self.assertEqual(count, 2)

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
