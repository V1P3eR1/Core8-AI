"""Standalone local SQLite receiver for testing at-least-once audit delivery.

REVIEW ONLY. This is a separate disposable database file from PostgreSQL,
but NOT a real remote immutable store, authenticated network endpoint, WORM
archive or production security boundary. The creator supplies the file path.
"""
import hashlib
import json
import re
import sqlite3
from tenant_access import FinanceAccessDenied

_EVENT = re.compile(r"^finance-approval-audit-[1-9][0-9]{0,18}$")


class SQLiteAuditReceiverCandidate:
    """Acknowledge only AFTER a committed insert or identical prior event."""

    def __init__(self, database_path):
        if (type(database_path) is not str or not database_path
                or database_path == ":memory:"):
            raise FinanceAccessDenied("Finance audit receiver denied")
        self.database_path = database_path

    def initialize_test_store(self):
        # Called only by trusted disposable test setup.
        with sqlite3.connect(self.database_path, timeout=10) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS received_audit_candidate (
                event_id TEXT PRIMARY KEY,
                payload_sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")

    def accept(self, event_id, payload):
        try:
            if (type(event_id) is not str or not _EVENT.fullmatch(event_id)
                    or type(payload) is not dict
                    or payload.get("event_id") != event_id
                    or payload.get("action") != "consumed"
                    or type(payload.get("approval_id")) is not str):
                raise ValueError("invalid audit event")
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                   allow_nan=False, ensure_ascii=True)
            if len(canonical.encode("ascii")) > 65536:
                raise ValueError("oversized audit event")
            fingerprint = hashlib.sha256(canonical.encode("ascii")).hexdigest()
            with sqlite3.connect(self.database_path, timeout=10) as db:
                db.execute(
                    """INSERT INTO received_audit_candidate
                       (event_id, payload_sha256, payload_json)
                       VALUES (?, ?, ?) ON CONFLICT(event_id) DO NOTHING""",
                    (event_id, fingerprint, canonical),
                )
                row = db.execute(
                    "SELECT payload_sha256 FROM received_audit_candidate WHERE event_id=?",
                    (event_id,),
                ).fetchone()
                if row is None or row[0] != fingerprint:
                    raise ValueError("replay with changed content")
            return True
        except (TypeError, ValueError, sqlite3.Error):
            raise FinanceAccessDenied("Finance audit receiver denied") from None
