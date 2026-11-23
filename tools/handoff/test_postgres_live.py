"""Live PostgreSQL concurrency tests. Run only against isolated CI test DB.

Disabled in default offline suite; CORE8_TEST_PG_DSN must explicitly point to
local DB named core8_ci_test. Never point this file at customer/production DB.
"""
import hashlib
import os
import threading
import unittest
from urllib.parse import urlparse

from postgres_replay_ledger import PostgresReplayLedger
from replay_ledger import ReplayBlocked

DSN = os.environ.get("CORE8_TEST_PG_DSN", "")


@unittest.skipUnless(DSN, "Requires isolated PostgreSQL CI service")
class PostgreSQLLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parsed = urlparse(DSN)
        if (parsed.scheme not in ("postgresql", "postgres")
                or parsed.hostname not in ("127.0.0.1", "localhost")
                or parsed.path != "/core8_ci_test"):
            raise RuntimeError("isolated_local_ci_database_required")
        import psycopg
        cls.factory = lambda: psycopg.connect(DSN, connect_timeout=5)
        cls.ledger = PostgresReplayLedger(cls.factory)
        cls.ledger.install_schema()

    def setUp(self):
        digest = hashlib.sha256(os.urandom(32)).hexdigest()
        self.fields = dict(repo="V1P3eR1/Core8-AI", run_id=123,
                           artifact_id=456, task_digest=digest,
                           patch_sha256="b"*64)

    def test_reserve_consume_commits(self):
        self.ledger.reserve(**self.fields)
        self.assertEqual(self.ledger.state(repo=self.fields["repo"], run_id=123,
                                           artifact_id=456), "RESERVED")
        self.ledger.mark_consumed(**self.fields)
        self.assertEqual(self.ledger.state(repo=self.fields["repo"], run_id=123,
                                           artifact_id=456), "CONSUMED")

    def test_replay_different_artifact_cannot_reuse_task(self):
        self.ledger.reserve(**self.fields)
        with self.assertRaises(ReplayBlocked):
            self.ledger.reserve(**{**self.fields, "run_id": 124, "artifact_id": 457})
        self.assertEqual(self.ledger.state(repo=self.fields["repo"], run_id=123,
                                           artifact_id=456), "RESERVED")

    def test_failed_consumption_preserves_reservation(self):
        self.ledger.reserve(**self.fields)
        with self.assertRaises(ReplayBlocked):
            self.ledger.mark_consumed(**{**self.fields, "patch_sha256": "c"*64})
        self.assertEqual(self.ledger.state(repo=self.fields["repo"], run_id=123,
                                           artifact_id=456), "RESERVED")

    def test_parallel_distinct_runs_only_one_commits(self):
        results = []
        failures = []
        mutex = threading.Lock()
        def worker(i):
            args = {**self.fields, "run_id": 1000+i, "artifact_id": 2000+i}
            try:
                PostgresReplayLedger(self.factory).reserve(**args)
                outcome = "reserved"
            except ReplayBlocked:
                outcome = "blocked"
            except Exception as exc:
                with mutex:
                    failures.append(type(exc).__name__)
                return
            with mutex:
                results.append(outcome)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(failures, [], "database concurrency must not have errors")
        self.assertEqual(results.count("reserved"), 1)
        self.assertEqual(results.count("blocked"), 11)

    def test_consumed_reservation_not_reopened(self):
        self.ledger.reserve(**self.fields)
        self.ledger.mark_consumed(**self.fields)
        with self.assertRaises(ReplayBlocked):
            self.ledger.reserve(**{**self.fields, "run_id": 100, "artifact_id": 200})
        with self.assertRaises(ReplayBlocked):
            self.ledger.mark_consumed(**self.fields)


if __name__ == "__main__":
    unittest.main()
