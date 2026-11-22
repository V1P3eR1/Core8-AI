#!/usr/bin/env python3
"""Synthetic, offline-only cloud continuity contract check. No external services."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest
from pathlib import Path


def claim(db_path: Path, key: str) -> bool:
    """Atomic deduplication across independent worker processes."""
    connection = sqlite3.connect(db_path, timeout=10)
    try:
        with connection:
            connection.execute("CREATE TABLE IF NOT EXISTS jobs (idempotency_key TEXT PRIMARY KEY, status TEXT NOT NULL)")
            result = connection.execute("INSERT OR IGNORE INTO jobs VALUES (?, 'queued')", (key,))
            return result.rowcount == 1
    finally:
        connection.close()


def checkpoint(db_path: Path, key: str, status: str) -> None:
    if status not in {"running", "review", "blocked", "failed"}:
        raise ValueError("unsupported state")
    connection = sqlite3.connect(db_path, timeout=10)
    try:
        with connection:
            result = connection.execute("UPDATE jobs SET status = ? WHERE idempotency_key = ?", (status, key))
            if result.rowcount != 1:
                raise KeyError(key)
    finally:
        connection.close()


def read_state(db_path: Path, key: str) -> str:
    connection = sqlite3.connect(db_path)
    try:
        try:
            row = connection.execute("SELECT status FROM jobs WHERE idempotency_key = ?", (key,)).fetchone()
        except sqlite3.OperationalError as error:
            if "no such table" in str(error):
                raise KeyError(key) from error
            raise
        if row is None:
            raise KeyError(key)
        return row[0]
    finally:
        connection.close()


class ContinuityContract(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / "synthetic.sqlite"

    def test_replay_does_not_duplicate(self):
        self.assertTrue(claim(self.db, "synthetic-task-1"))
        self.assertFalse(claim(self.db, "synthetic-task-1"))
        self.assertEqual(read_state(self.db, "synthetic-task-1"), "queued")

    def test_concurrent_claims_have_one_winner(self):
        # Prime the schema to avoid confusing DDL races with claim contention.
        claim(self.db, 'schema-primer')
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: claim(self.db, 'same-task'), range(24)))
        self.assertEqual(sum(results), 1)

    def test_missing_state_is_keyerror(self):
        with self.assertRaises(KeyError):
            read_state(self.db, 'missing')

    def test_checkpoint_survives_reopen(self):
        claim(self.db, "synthetic-task-2")
        checkpoint(self.db, "synthetic-task-2", "running")
        self.assertEqual(read_state(self.db, "synthetic-task-2"), "running")
        checkpoint(self.db, "synthetic-task-2", "review")
        self.assertEqual(read_state(self.db, "synthetic-task-2"), "review")

    def test_approval_pause_is_isolated(self):
        claim(self.db, "needs-approval")
        claim(self.db, "independent-job")
        checkpoint(self.db, "needs-approval", "blocked")
        checkpoint(self.db, "independent-job", "review")
        self.assertEqual(read_state(self.db, "needs-approval"), "blocked")
        self.assertEqual(read_state(self.db, "independent-job"), "review")

    def test_invalid_transition_rejected(self):
        claim(self.db, "synthetic-task-3")
        with self.assertRaises(ValueError):
            checkpoint(self.db, "synthetic-task-3", "published")
        self.assertEqual(read_state(self.db, "synthetic-task-3"), "queued")


if __name__ == "__main__":
    unittest.main(verbosity=2)
