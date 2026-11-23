"""Offline webhook credential rotation policy.

A trusted server registry may hold an active key and a temporary previous key.
Never load secrets from HTTP request fields. No production credential storage.
"""
from webhook_signature_demo import verify

def verify_rotating_credential(credential, timestamp, raw_body, signature_hex, *, now, delivery_id=None):
    if not isinstance(credential, dict) or credential.get("active") is not True:
        return {"ok": False, "reason": "inactive_credential"}
    current = credential.get("secret")
    previous = credential.get("previous_secret")
    previous_until = credential.get("previous_valid_until")
    primary = verify(current, timestamp, raw_body, signature_hex, now=now, delivery_id=delivery_id)
    if primary["ok"]:
        return {"ok": True, "key_version": "current"}
    if primary["reason"] != "signature_mismatch":
        return primary
    # Do not use an expired or malformed previous-key grace period.
    if not isinstance(previous_until, int) or isinstance(previous_until, bool):
        return {"ok": False, "reason": "signature_mismatch"}
    if now > previous_until or not isinstance(previous, bytes) or not previous:
        return {"ok": False, "reason": "signature_mismatch"}
    alternate = verify(previous, timestamp, raw_body, signature_hex, now=now)
    if alternate["ok"]:
        return {"ok": True, "key_version": "previous"}
    return {"ok": False, "reason": "signature_mismatch"}
