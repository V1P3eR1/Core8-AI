"""Disposable standalone SQLite generation-floor candidate.

Test-only, stored in a separate local SQLite file from Finance PostgreSQL.
Atomic SQLite CAS across threads/processes sharing the same file is exercised,
but this is NOT a separately administered, authenticated, tamper-resistant
production authority. A file owner or full-disk backup restore can roll it back.
No HTTP, no background task, no production deployment.
"""
import re
import sqlite3
from pathlib import Path

from external_floor_candidate import IndependentGenerationFloor
from tenant_access import FinanceAccessDenied

_NAMESPACE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")


class SQLiteGenerationFloorCandidate(IndependentGenerationFloor):
    def __init__(self, *, path):
        if (type(path) is not str or not path or path == ":memory:"
                or path.startswith("file:") or "\x00" in path):
            raise FinanceAccessDenied("Finance floor denied")
        self.path = path

    def initialize_test_store(self):
        """Test administrator only; does not grant production floor authority."""
        try:
            if not Path(self.path).parent.is_dir():
                raise ValueError("parent missing")
            with sqlite3.connect(self.path, timeout=10) as db:
                db.execute("""CREATE TABLE IF NOT EXISTS floor_candidate (
                    namespace TEXT PRIMARY KEY,
                    generation INTEGER NOT NULL CHECK (generation >= 1)
                )""")
        except (sqlite3.Error, ValueError, OSError):
            raise FinanceAccessDenied("Finance floor denied") from None

    @staticmethod
    def _namespace(namespace):
        if type(namespace) is not str or not _NAMESPACE.fullmatch(namespace):
            raise FinanceAccessDenied("Finance floor denied")

    def provision_test_namespace(self, namespace):
        """Explicit once-only disposable test provisioning."""
        self._namespace(namespace)
        try:
            with sqlite3.connect(self.path, timeout=10) as db:
                result = db.execute(
                    "INSERT INTO floor_candidate(namespace, generation) "
                    "VALUES (?, 1) ON CONFLICT(namespace) DO NOTHING",
                    (namespace,),
                )
                if result.rowcount != 1:
                    raise FinanceAccessDenied("Finance floor denied")
        except sqlite3.Error:
            raise FinanceAccessDenied("Finance floor denied") from None

    def read(self, namespace):
        self._namespace(namespace)
        try:
            # URI mode=ro refuses to create an absent database on read.
            from urllib.parse import quote
            uri = "file:" + quote(str(Path(self.path).resolve())) + "?mode=ro"
            with sqlite3.connect(uri, timeout=10, uri=True) as db:
                row = db.execute(
                    "SELECT generation FROM floor_candidate WHERE namespace=?",
                    (namespace,),
                ).fetchone()
            if row is None or type(row[0]) is not int or row[0] < 1:
                raise FinanceAccessDenied("Finance floor denied")
            return row[0]
        except (sqlite3.Error, OSError):
            raise FinanceAccessDenied("Finance floor denied") from None

    def compare_and_advance(self, namespace, expected_generation, next_generation):
        self._namespace(namespace)
        if (type(expected_generation) is not int or expected_generation < 1
                or type(next_generation) is not int
                or next_generation != expected_generation + 1):
            raise FinanceAccessDenied("Finance floor denied")
        try:
            with sqlite3.connect(self.path, timeout=10) as db:
                # One UPDATE is a SQLite atomic conditional write.
                cur = db.execute(
                    "UPDATE floor_candidate SET generation=? "
                    "WHERE namespace=? AND generation=?",
                    (next_generation, namespace, expected_generation),
                )
                if cur.rowcount == 1:
                    return True
                # Stale CAS is a safe negative result, but missing table or
                # missing namespace must never be mistaken for a stale update.
                row = db.execute(
                    "SELECT generation FROM floor_candidate WHERE namespace=?",
                    (namespace,),
                ).fetchone()
                if row is None:
                    raise FinanceAccessDenied("Finance floor denied")
                return False
        except sqlite3.Error:
            raise FinanceAccessDenied("Finance floor denied") from None
