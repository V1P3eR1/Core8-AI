#!/usr/bin/env python3
"""Synthetic, offline-only cloud continuity contract check. No external services."""
import sqlite3
from concurrent.futures import ProcessPoolExecutor
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
    allowed = {
        "queued": {"running", "blocked"},
        "running": {"review", "blocked", "failed"},
        "review": set(),
        "blocked": set(),
        "failed": set(),
    }
    if status not in {"running", "review", "blocked", "failed"}:
        raise ValueError("unsupported state")
    connection = sqlite3.connect(db_path, timeout=10)
    try:
        with connection:
            row = connection.execute("SELECT status FROM jobs WHERE idempotency_key = ?", (key,)).fetchone()
            if row is None:
                raise KeyError(key)
            previous = row[0]
            if status not in allowed.get(previous, set()):
                raise ValueError("transition requires a new approved job revision")
            result = connection.execute(
                "UPDATE jobs SET status = ? WHERE idempotency_key = ? AND status = ?",
                (status, key, previous),
            )
            if result.rowcount != 1:
                raise ValueError("concurrent transition conflict")
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


def claim_worker(args):
    """Top-level picklable entrypoint for independent process contention."""
    db_path, key = args
    return claim(db_path, key)


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
        with ProcessPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(claim_worker, [(self.db, 'same-task')] * 16))
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
        checkpoint(self.db, "independent-job", "running")
        checkpoint(self.db, "independent-job", "review")
        self.assertEqual(read_state(self.db, "needs-approval"), "blocked")
        self.assertEqual(read_state(self.db, "independent-job"), "review")

    def test_blocked_job_cannot_resume_without_new_revision(self):
        claim(self.db, "requires-owner-approval")
        checkpoint(self.db, "requires-owner-approval", "blocked")
        with self.assertRaisesRegex(ValueError, "new approved job revision"):
            checkpoint(self.db, "requires-owner-approval", "running")
        self.assertEqual(read_state(self.db, "requires-owner-approval"), "blocked")

    def test_review_cannot_return_to_running(self):
        claim(self.db, "already-reviewed")
        checkpoint(self.db, "already-reviewed", "running")
        checkpoint(self.db, "already-reviewed", "review")
        with self.assertRaises(ValueError):
            checkpoint(self.db, "already-reviewed", "running")

    def test_queued_job_cannot_skip_running_for_review(self):
        claim(self.db, "skipped-step")
        with self.assertRaises(ValueError):
            checkpoint(self.db, "skipped-step", "review")
        self.assertEqual(read_state(self.db, "skipped-step"), "queued")

    def test_invalid_transition_rejected(self):
        claim(self.db, "synthetic-task-3")
        with self.assertRaises(ValueError):
            checkpoint(self.db, "synthetic-task-3", "published")
        self.assertEqual(read_state(self.db, "synthetic-task-3"), "queued")


if __name__ == "__main__":
    unittest.main(verbosity=2)
