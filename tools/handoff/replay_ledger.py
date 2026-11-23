"""Atomic local replay reservations for reviewed Claude artifacts.

Offline SQLite component. NOT an action, external lock service, or authority to run.
Never use :memory: or per-run ephemeral storage for a distributed runner.
"""
import re
import sqlite3
from pathlib import Path


class ReplayBlocked(ValueError):
    """Reject duplicate, malformed or conflicting artifact reservations."""


def _check_text(value, regex):
    if not isinstance(value, str) or not re.fullmatch(regex, value):
        raise ReplayBlocked("invalid_identity")
    return value


def _check_id(value):
    if type(value) is not int or value <= 0:
        raise ReplayBlocked("invalid_identifier")
    return value


class ReplayLedger:
    def __init__(self, path):
        self.path = Path(path)
        if str(path) == ":memory:" or self.path.is_dir():
            raise ReplayBlocked("persistent_storage_required")
        if not self.path.parent.exists():
            raise ReplayBlocked("storage_directory_missing")
        # Caller must provision a secured durable path; no secret is stored.
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS reservations(
                    repo TEXT NOT NULL,
                    run_id INTEGER NOT NULL,
                    artifact_id INTEGER NOT NULL,
                    task_digest TEXT NOT NULL,
                    patch_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('RESERVED', 'CONSUMED')),
                    PRIMARY KEY(repo, run_id, artifact_id)
                )"""
            )
            # Preserve at-most-once semantics across DIFFERENT runs/artifacts
            # for the same approved task revision. An existing ledger with
            # ambiguous duplicate tasks must fail closed on migration.
            try:
                db.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS reservations_one_task "
                    "ON reservations(repo, task_digest)"
                )
            except sqlite3.IntegrityError:
                raise ReplayBlocked("ambiguous_existing_task_reservations") from None

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @staticmethod
    def _fields(repo, run_id, artifact_id, task_digest, patch_sha256):
        return (_check_text(repo, r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"),
                _check_id(run_id), _check_id(artifact_id),
                _check_text(task_digest, r"[0-9a-f]{64}"),
                _check_text(patch_sha256, r"[0-9a-f]{64}"))

    def reserve(self, *, repo, run_id, artifact_id, task_digest, patch_sha256):
        """Fail-closed on any repeated reservation, including abandoned runs."""
        fields = self._fields(repo, run_id, artifact_id, task_digest, patch_sha256)
        with self._connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "INSERT INTO reservations VALUES (?, ?, ?, ?, ?, 'RESERVED')",
                    fields
                )
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
                raise ReplayBlocked("already_reserved") from None

    def mark_consumed(self, *, repo, run_id, artifact_id, task_digest, patch_sha256):
        """Only transitions a matching reservation once, in a transaction."""
        fields = self._fields(repo, run_id, artifact_id, task_digest, patch_sha256)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                """UPDATE reservations SET state='CONSUMED'
                WHERE repo=? AND run_id=? AND artifact_id=?
                AND task_digest=? AND patch_sha256=? AND state='RESERVED'""",
                fields
            )
            if cursor.rowcount != 1:
                db.rollback()
                raise ReplayBlocked("missing_mismatched_or_consumed")
            db.commit()

    def state(self, *, repo, run_id, artifact_id):
        repo = _check_text(repo, r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
        run_id, artifact_id = _check_id(run_id), _check_id(artifact_id)
        with self._connect() as db:
            row = db.execute(
                "SELECT state FROM reservations WHERE repo=? AND run_id=? AND artifact_id=?",
                (repo, run_id, artifact_id),
            ).fetchone()
        return row[0] if row else None
