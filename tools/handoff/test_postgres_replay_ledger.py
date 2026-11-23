import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from postgres_replay_ledger import (PostgresReplayLedger, CREATE_SCHEMA,
                                    RESERVE_SQL, CONSUME_SQL)
from replay_ledger import ReplayBlocked


# SQLite is a deterministic test double for SQL statement and transaction
# behavior, NOT a claim that PostgreSQL has been integration-tested.
class CursorAdapter:
    def __init__(self, connection):
        self.conn = connection
        self.cur = None
    def __enter__(self):
        self.cur = self.conn.cursor()
        return self
    def __exit__(self, *_):
        self.cur.close()
    def execute(self, query, values=()):
        self.cur.execute(query.replace("%s", "?"), values)
    def fetchone(self):
        return self.cur.fetchone()


class ConnectionAdapter:
    def __init__(self, path):
        self.path = path
        self.conn = None
    def __enter__(self):
        self.conn = sqlite3.connect(self.path, timeout=10)
        return self
    def __exit__(self, kind, value, trace):
        try:
            if kind is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            self.conn.close()
    def cursor(self):
        return CursorAdapter(self.conn)


class PostgreSQLReplayContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "test.sqlite"
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TABLE core8_replay_reservations(
                repo TEXT NOT NULL, task_digest TEXT NOT NULL,
                run_id INTEGER NOT NULL, artifact_id INTEGER NOT NULL,
                patch_sha256 TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'RESERVED',
                consumed_at TEXT,
                PRIMARY KEY(repo, task_digest),
                UNIQUE(repo, run_id, artifact_id)
            )""")
        self.ledger = PostgresReplayLedger(lambda: ConnectionAdapter(self.path))
        self.fields = dict(repo="V1P3eR1/Core8-AI", task_digest="a"*64,
                           run_id=123, artifact_id=456, patch_sha256="b"*64)

    def test_ddl_has_both_independent_unique_keys(self):
        self.assertIn("PRIMARY KEY (repo, task_digest)", CREATE_SCHEMA)
        self.assertIn("UNIQUE (repo, run_id, artifact_id)", CREATE_SCHEMA)
        self.assertIn("TIMESTAMPTZ", CREATE_SCHEMA)

    def test_conflicts_are_not_rewritten_or_released(self):
        self.assertIn("ON CONFLICT DO NOTHING RETURNING state", RESERVE_SQL)
        self.assertNotIn("DELETE", RESERVE_SQL.upper())
        self.assertNotIn("UPSERT", RESERVE_SQL.upper())
        self.assertIn("AND state = 'RESERVED'", CONSUME_SQL)

    def test_state_initially_missing(self):
        self.assertIsNone(self.ledger.state(repo=self.fields["repo"], run_id=123, artifact_id=456))

    def test_reserve_and_consume(self):
        self.ledger.reserve(**self.fields)
        self.assertEqual(self.ledger.state(repo=self.fields["repo"], run_id=123,
                                           artifact_id=456), "RESERVED")
        self.ledger.mark_consumed(**self.fields)
        self.assertEqual(self.ledger.state(repo=self.fields["repo"], run_id=123,
                                           artifact_id=456), "CONSUMED")

    def test_same_task_different_artifact_rejected(self):
        self.ledger.reserve(**self.fields)
        with self.assertRaisesRegex(ReplayBlocked, "already_reserved"):
            self.ledger.reserve(**{**self.fields, "run_id": 999, "artifact_id": 888})

    def test_same_provider_artifact_different_task_rejected(self):
        self.ledger.reserve(**self.fields)
        with self.assertRaises(ReplayBlocked):
            self.ledger.reserve(**{**self.fields, "task_digest": "c"*64})

    def test_different_task_and_artifact_allowed(self):
        self.ledger.reserve(**self.fields)
        self.ledger.reserve(**{**self.fields, "run_id": 321, "artifact_id": 654,
                               "task_digest": "c"*64})

    def test_consuming_other_hash_does_not_consume(self):
        self.ledger.reserve(**self.fields)
        with self.assertRaises(ReplayBlocked):
            self.ledger.mark_consumed(**{**self.fields, "patch_sha256": "d"*64})
        self.assertEqual(self.ledger.state(repo=self.fields["repo"], run_id=123,
                                           artifact_id=456), "RESERVED")

    def test_consumed_cannot_be_reused(self):
        self.ledger.reserve(**self.fields)
        self.ledger.mark_consumed(**self.fields)
        with self.assertRaises(ReplayBlocked):
            self.ledger.reserve(**{**self.fields, "run_id": 222, "artifact_id": 777})
        with self.assertRaises(ReplayBlocked):
            self.ledger.mark_consumed(**self.fields)

    def test_invalid_data_cannot_reach_database(self):
        cases = [
            {"run_id": True}, {"run_id": 2**63},
            {"artifact_id": -1}, {"repo": "../evil"},
            {"task_digest": "not-a-digest"}, {"patch_sha256": "A"*64},
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ReplayBlocked):
                self.ledger.reserve(**{**self.fields, **case})

    def test_missing_factory_blocks(self):
        with self.assertRaisesRegex(ReplayBlocked, "missing_trusted_database_connection"):
            PostgresReplayLedger(None)

    def test_parallel_cross_runner_shape_only_one_wins(self):
        results = []
        lock = threading.Lock()
        def worker(i):
            args = dict(self.fields, run_id=1000+i, artifact_id=2000+i)
            try:
                PostgresReplayLedger(lambda: ConnectionAdapter(self.path)).reserve(**args)
                outcome = "reserved"
            except ReplayBlocked:
                outcome = "blocked"
            with lock:
                results.append(outcome)
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(results.count("reserved"), 1)
        self.assertEqual(results.count("blocked"), 7)


if __name__ == "__main__":
    unittest.main()
