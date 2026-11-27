"""Offline end-to-end lead intake orchestration (synthetic data only).

No HTTP endpoint, no production DB, no outgoing messages. The caller must
supply verified identity and trusted server-fetched membership records.
"""
import hashlib
import json
from tenant_auth_demo import resolve_tenant
from sqlite_atomic_ingest_demo import ingest

def canonical_payload_digest(payload):
    """Deterministic demo digest; production canonicalization needs versioning."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def preview_intake(conn, *, identity, memberships, requested_tenant_id,
                   source_system, submission_id, lead_id, name, payload):
    access = resolve_tenant(identity=identity,
                            requested_tenant_id=requested_tenant_id,
                            memberships=memberships)
    if not access["ok"]:
        return {"ok": False, "reason": access["reason"]}
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "invalid_payload"}
    if payload.get("consent") is not True:
        return {"ok": False, "reason": "consent_required"}
    if payload.get("source_verified") is not True:
        return {"ok": False, "reason": "source_unverified"}
    if not isinstance(name, str) or not name.strip():
        return {"ok": False, "reason": "invalid_name"}
    try:
        digest = canonical_payload_digest(payload)
        result = ingest(
            conn, trusted_tenant_id=access["trusted_tenant_id"],
            source_system=source_system, submission_id=submission_id,
            lead_id=lead_id, payload_sha256=digest, name=name
        )
    except (TypeError, ValueError, OverflowError):
        return {"ok": False, "reason": "invalid_payload"}
    return result
