"""Offline signed intake boundary: trusted credential registry, HMAC and atomic SQLite.

Only synthetic credentials/data. No HTTP endpoint, secrets store, or production DB.
"""
import json
from webhook_signature_demo import verify
from sqlite_atomic_ingest_demo import ingest
from offline_intake_demo import canonical_payload_digest

def signed_intake(conn, *, raw_body, timestamp, signature_hex,
                  credential_id, credential_registry, now, lead_id):
    # Registry is trusted server configuration; never supplied by the HTTP client.
    if not isinstance(credential_registry, dict) or not isinstance(credential_id, str):
        return {"ok": False, "reason": "invalid_registry"}
    credential = credential_registry.get(credential_id)
    if not isinstance(credential, dict) or credential.get("active") is not True:
        return {"ok": False, "reason": "unknown_credential"}
    tenant = credential.get("tenant_id")
    source = credential.get("source_system")
    secret = credential.get("secret")
    if not isinstance(tenant, str) or not tenant or not isinstance(source, str) or not source:
        return {"ok": False, "reason": "invalid_registry"}
    verified = verify(secret, timestamp, raw_body, signature_hex, now=now)
    if not verified["ok"]:
        return {"ok": False, "reason": verified["reason"]}
    try:
        payload = json.loads(raw_body)
    except (ValueError, TypeError, UnicodeDecodeError):
        return {"ok": False, "reason": "invalid_json"}
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "invalid_payload"}
    if payload.get("consent") is not True:
        return {"ok": False, "reason": "consent_required"}
    submission = payload.get("submission_id")
    name = payload.get("name")
    if not isinstance(submission, str) or not submission or len(submission) > 256:
        return {"ok": False, "reason": "invalid_submission"}
    if not isinstance(name, str) or not name.strip() or len(name) > 256:
        return {"ok": False, "reason": "invalid_name"}
    # A payload-provided tenant/source is never used as authority.
    digest = canonical_payload_digest(payload)
    return ingest(conn, trusted_tenant_id=tenant, source_system=source,
                  submission_id=submission, lead_id=lead_id,
                  payload_sha256=digest, name=name)
