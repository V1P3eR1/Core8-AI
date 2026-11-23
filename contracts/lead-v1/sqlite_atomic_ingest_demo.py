"""Disposable SQLite proof of atomic claim + lead creation. Not a platform migration."""
import sqlite3

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE demo_leads (
 tenant_id TEXT NOT NULL,
 id TEXT NOT NULL,
 name TEXT NOT NULL,
 PRIMARY KEY (tenant_id, id)
);
CREATE TABLE demo_claims (
 tenant_id TEXT NOT NULL,
 source_system TEXT NOT NULL,
 submission_id TEXT NOT NULL,
 lead_id TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 PRIMARY KEY (tenant_id, source_system, submission_id),
 FOREIGN KEY (tenant_id, lead_id) REFERENCES demo_leads(tenant_id, id)
);
"""

def setup(conn):
    conn.executescript(SCHEMA)

def ingest(conn, *, trusted_tenant_id, source_system, submission_id,
           lead_id, payload_sha256, name, fail_after_lead=False):
    """Trusted tenant must be resolved by a server. Never use this as auth."""
    if not all(isinstance(x, str) and x for x in
               (trusted_tenant_id, source_system, submission_id,
                lead_id, payload_sha256, name)):
        raise ValueError("invalid_input")
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT lead_id, payload_sha256 FROM demo_claims WHERE tenant_id=? AND source_system=? AND submission_id=?",
            (trusted_tenant_id, source_system, submission_id)
        ).fetchone()
        if row:
            conn.commit()
            if row[1] != payload_sha256:
                return {"ok": False, "conflict": True}
            return {"ok": True, "lead_id": row[0], "replayed": True}
        conn.execute(
            "INSERT INTO demo_leads (tenant_id,id,name) VALUES (?,?,?)",
            (trusted_tenant_id, lead_id, name)
        )
        if fail_after_lead:
            raise RuntimeError("injected_failure_before_claim")
        conn.execute(
            "INSERT INTO demo_claims (tenant_id,source_system,submission_id,lead_id,payload_sha256) VALUES (?,?,?,?,?)",
            (trusted_tenant_id, source_system, submission_id, lead_id, payload_sha256)
        )
        conn.commit()
        return {"ok": True, "lead_id": lead_id, "replayed": False}
    except BaseException:
        conn.rollback()
        raise
