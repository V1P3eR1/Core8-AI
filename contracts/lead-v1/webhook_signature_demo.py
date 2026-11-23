"""Offline signed webhook fixture with replay-window validation.

Demonstration only: no HTTP endpoint, credential store or external requests.
The signing secret must be resolved from trusted server configuration.
"""
import hashlib
import hmac
import time

MAX_AGE_SECONDS = 300

def signature(secret, timestamp, body, *, delivery_id=None):
    if not isinstance(secret, bytes) or not secret:
        raise ValueError("invalid_secret")
    if not isinstance(body, bytes) or not isinstance(timestamp, int):
        raise ValueError("invalid_message")
    if delivery_id is None:
        data = str(timestamp).encode("ascii") + b"." + body
    else:
        if not isinstance(delivery_id, str) or not (1 <= len(delivery_id) <= 256) or not delivery_id.isascii():
            raise ValueError("invalid_delivery_id")
        # v2: explicit domain separator and length-prefixed delivery identity.
        identity = delivery_id.encode("ascii")
        data = b"core8-delivery-v2:" + str(timestamp).encode("ascii") + b":" + str(len(identity)).encode("ascii") + b":" + identity + b":" + body
    return hmac.new(secret, data, hashlib.sha256).hexdigest()

def verify(secret, timestamp, body, provided_signature, *, now=None, delivery_id=None):
    if not isinstance(timestamp, int) or isinstance(timestamp, bool):
        return {"ok": False, "reason": "invalid_timestamp"}
    current = int(time.time()) if now is None else now
    if not isinstance(current, int) or isinstance(current, bool):
        return {"ok": False, "reason": "invalid_clock"}
    if timestamp > current + 30 or current - timestamp > MAX_AGE_SECONDS:
        return {"ok": False, "reason": "outside_replay_window"}
    if not isinstance(body, bytes) or len(body) > 65536:
        return {"ok": False, "reason": "invalid_body"}
    if not isinstance(provided_signature, str) or len(provided_signature) != 64:
        return {"ok": False, "reason": "invalid_signature"}
    try:
        expected = signature(secret, timestamp, body, delivery_id=delivery_id)
    except ValueError:
        return {"ok": False, "reason": "invalid_secret"}
    if not hmac.compare_digest(expected, provided_signature):
        return {"ok": False, "reason": "signature_mismatch"}
    return {"ok": True}
