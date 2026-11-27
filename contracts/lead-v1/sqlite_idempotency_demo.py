"""Disposable SQLite idempotency proof. Never imports or writes platform DB."""
import sqlite3

DDL = """
CREATE TABLE IF NOT EXISTS demo_claims (
 tenant_id TEXT NOT NULL,
 source_system TEXT NOT NULL,
 submission_id TEXT NOT NULL,
 lead_id TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 PRIMARY KEY (tenant_id, source_system, submission_id),
 UNIQUE (tenant_id, lead_id)
);
"""

def setup(conn):
    conn.executescript(DDL)

def claim(conn, *, tenant_id, source_system, submission_id, lead_id, payload_sha256):
    """Caller must supply trusted tenant context; not an authorization function."""
    if not all(isinstance(v, str) and v for v in
               (tenant_id, source_system, submission_id, lead_id, payload_sha256)):
        raise ValueError("invalid claim")
    with conn:
        conn.execute(
            """INSERT INTO demo_claims
               (tenant_id, source_system, submission_id, lead_id, payload_sha256)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(tenant_id, source_system, submission_id) DO NOTHING""",
            (tenant_id, source_system, submission_id, lead_id, payload_sha256),
        )
        row = conn.execute(
            """SELECT lead_id, payload_sha256 FROM demo_claims
               WHERE tenant_id=? AND source_system=? AND submission_id=?""",
            (tenant_id, source_system, submission_id),
        ).fetchone()
    if row[1] != payload_sha256:
        return {"ok": False, "conflict": True}
    return {"ok": True, "lead_id": row[0], "replayed": row[0] != lead_id}
