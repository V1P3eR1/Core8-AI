"""Sandbox-only authenticated JWKS registry state export/import.

The caller must supply a strong secret from an independent trusted secret store
AND a durable externally enforced minimum generation (anti-rollback floor).
A signed snapshot ALONE does not prevent replay of an older signed snapshot.
No disk, network, env, secrets manager, HTTP route or live provider is accessed.
"""
import base64
import hashlib
import hmac
import json

from pinned_jwks_candidate import PinnedJwksRegistry, _validate_public_keys
from tenant_access import FinanceAccessDenied

MAX_BLOB_BYTES = 64 * 1024
STATE_FORMAT = "core8.finance.jwks.snapshot.v1"


def _mac(key, payload):
    return hmac.new(key, payload, hashlib.sha256).digest()


def export_registry_state(registry, *, signing_key):
    """Return authenticated bytes for an external trusted durable store."""
    if type(registry) is not PinnedJwksRegistry or type(signing_key) is not bytes or len(signing_key) < 32:
        raise FinanceAccessDenied("Finance key configuration denied")
    with registry._lock:
        state = {
            "format": STATE_FORMAT,
            "generation": registry._generation,
            "keys": list(registry._keys.values()),
            "retired": sorted(registry._retired),
        }
        raw = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        if len(raw) > MAX_BLOB_BYTES:
            raise FinanceAccessDenied("Finance key configuration denied")
        envelope = {
            "state": state,
            "mac": base64.urlsafe_b64encode(_mac(signing_key, raw)).decode("ascii"),
        }
        return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("ascii")


def import_registry_state(blob, *, signing_key, minimum_generation):
    """Validate signed state AND external anti-rollback floor before recovery.

    The caller MUST store the high-watermark generation outside the snapshot
    and update it atomically with any approved key transition. A process-local
    counter, self-contained signed file or user-provided floor is insufficient.
    """
    try:
        if (type(blob) is not bytes or len(blob) > MAX_BLOB_BYTES or
                type(signing_key) is not bytes or len(signing_key) < 32 or
                type(minimum_generation) is not int or minimum_generation < 1):
            raise ValueError("invalid input")
        envelope = json.loads(blob)
        if type(envelope) is not dict or set(envelope) != {"state", "mac"}:
            raise ValueError("invalid envelope")
        state = envelope["state"]
        if type(state) is not dict or set(state) != {"format", "generation", "keys", "retired"}:
            raise ValueError("invalid state")
        raw = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        encoded_mac = envelope["mac"]
        if type(encoded_mac) is not str:
            raise ValueError("invalid MAC")
        tag = base64.urlsafe_b64decode(encoded_mac)
        if not hmac.compare_digest(_mac(signing_key, raw), tag):
            raise ValueError("invalid signature")
        gen = state["generation"]
        if state["format"] != STATE_FORMAT or type(gen) is not int or gen < minimum_generation:
            raise ValueError("stale generation")
        if (type(state["retired"]) is not list or
                any(type(k) is not str for k in state["retired"]) or
                len(set(state["retired"])) != len(state["retired"])):
            raise ValueError("invalid revocation list")
        keyset = _validate_public_keys({"keys": state["keys"]})
        retired = set(state["retired"])
        if retired & set(keyset):
            raise ValueError("retired key reintroduced")
        registry = PinnedJwksRegistry({"keys": list(keyset.values())}, generation=gen)
        registry._retired = retired
        return registry
    except Exception:
        raise FinanceAccessDenied("Finance key configuration denied") from None
