"""Offline atomic webhook event receipt + lead creation with replay rejection.

Unlike lead idempotency, this rejects a repeated signed delivery entirely.
Only an isolated SQLite fixture; no production migrations or HTTP endpoints.
"""

def setup_receipts(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS demo_receipts (
        tenant_id TEXT NOT NULL,
        source_system TEXT NOT NULL,
        delivery_id TEXT NOT NULL,
        PRIMARY KEY (tenant_id, source_system, delivery_id)
    )""")
    conn.commit()

def receive_once(conn, *, delivery_id, raw_body, timestamp, signature_hex,
                 credential_id, credential_registry, now, lead_id):
    if not isinstance(delivery_id, str) or not (1 <= len(delivery_id) <= 256):
        return {"ok": False, "reason": "invalid_delivery_id"}
    credential = credential_registry.get(credential_id) if isinstance(credential_registry, dict) else None
    if not isinstance(credential, dict) or credential.get("active") is not True:
        return {"ok": False, "reason": "unknown_credential"}
    tenant, source = credential.get("tenant_id"), credential.get("source_system")
    if not isinstance(tenant, str) or not tenant or not isinstance(source, str) or not source:
        return {"ok": False, "reason": "invalid_registry"}
    # Verify cryptographic provenance before reserving a receipt.
    from credential_rotation_demo import verify_rotating_credential
    verified = verify_rotating_credential(credential, timestamp, raw_body, signature_hex, now=now)
    if not verified["ok"]:
        return verified
    # Receipt and lead must share one SQLite transaction; no nested transaction.
    import json
    from offline_intake_demo import canonical_payload_digest
    try:
        payload = json.loads(raw_body)
    except (ValueError, TypeError, UnicodeDecodeError):
        return {"ok": False, "reason": "invalid_json"}
    if not isinstance(payload, dict) or payload.get("consent") is not True:
        return {"ok": False, "reason": "consent_required"}
    submission, name = payload.get("submission_id"), payload.get("name")
    if not isinstance(submission, str) or not submission or len(submission) > 256:
        return {"ok": False, "reason": "invalid_submission"}
    if not isinstance(name, str) or not name.strip() or len(name) > 256:
        return {"ok": False, "reason": "invalid_name"}
    digest = canonical_payload_digest(payload)
    conn.execute("BEGIN IMMEDIATE")
    try:
        prior = conn.execute(
            "SELECT 1 FROM demo_receipts WHERE tenant_id=? AND source_system=? AND delivery_id=?",
            (tenant, source, delivery_id)).fetchone()
        if prior:
            conn.commit()
            return {"ok": False, "reason": "delivery_replayed"}
        row = conn.execute(
            "SELECT lead_id,payload_sha256 FROM demo_claims WHERE tenant_id=? AND source_system=? AND submission_id=?",
            (tenant, source, submission)).fetchone()
        if row and row[1] != digest:
            conn.commit()
            return {"ok": False, "reason": "payload_conflict"}
        if not row:
            conn.execute("INSERT INTO demo_leads (tenant_id,id,name) VALUES (?,?,?)",
                         (tenant, lead_id, name))
            conn.execute(
                "INSERT INTO demo_claims (tenant_id,source_system,submission_id,lead_id,payload_sha256) VALUES (?,?,?,?,?)",
                (tenant, source, submission, lead_id, digest))
        conn.execute(
            "INSERT INTO demo_receipts (tenant_id,source_system,delivery_id) VALUES (?,?,?)",
            (tenant, source, delivery_id))
        conn.commit()
        return {"ok": True, "lead_id": row[0] if row else lead_id,
                "replayed_lead": bool(row)}
    except BaseException:
        conn.rollback()
        raise
