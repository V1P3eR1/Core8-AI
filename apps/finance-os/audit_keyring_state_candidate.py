"""Signed, non-secret audit keyring snapshot contract (Sandbox only).

No key bytes are serialized. Trusted caller must independently resolve key
material by kid from a KMS/secret store, provide a separate signing secret,
and obtain a durable *external* generation floor. The snapshot is not an
encrypted secret store or a production persistence implementation.
"""
import base64
import hashlib
import hmac
import json
import re

from audit_key_rotation_candidate import AuditKeyringCandidate, PinnedAuditKey
from tenant_access import FinanceAccessDenied

_FORMAT = "core8.finance.audit-keyring.v1"
_KID = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_MAX_BYTES = 16384


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _signing_key(secret):
    if type(secret) is not bytes or len(secret) < 32:
        raise FinanceAccessDenied("Finance audit key snapshot denied")
    return secret


def export_audit_keyring_state(registry, *, signing_key):
    """Export a MAC-protected inventory of key IDs/digests and revocations."""
    if type(registry) is not AuditKeyringCandidate:
        raise FinanceAccessDenied("Finance audit key snapshot denied")
    secret = _signing_key(signing_key)
    with registry._lock:
        state = {
            "format": _FORMAT,
            "generation": registry.generation,
            "active": registry._active,
            "keys": [
                {"kid": kid, "sha256": hashlib.sha256(value).hexdigest()}
                for kid, value in sorted(registry._keys.items())
            ],
            "retired": sorted(registry._retired),
        }
        raw = _canonical(state)
    if len(raw) > _MAX_BYTES:
        raise FinanceAccessDenied("Finance audit key snapshot denied")
    envelope = {
        "state": state,
        "mac": base64.urlsafe_b64encode(
            hmac.new(secret, raw, hashlib.sha256).digest()
        ).decode("ascii"),
    }
    blob = _canonical(envelope)
    if len(blob) > _MAX_BYTES:
        raise FinanceAccessDenied("Finance audit key snapshot denied")
    return blob


def import_audit_keyring_state(blob, *, signing_key, expected_generation,
                               trusted_key_material):
    """Recover only exact externally verified generation, no material in blob.

    trusted_key_material must be a separately administered mapping of exact
    {kid: bytes} resolved by trusted configuration, NEVER supplied by a client.
    expected_generation must come from independently durable monotonic CAS,
    not from the snapshot or request. Invalid snapshots fail closed.
    """
    try:
        secret = _signing_key(signing_key)
        if (type(blob) is not bytes or len(blob) > _MAX_BYTES
                or type(expected_generation) is not int
                or expected_generation < 1
                or type(trusted_key_material) is not dict):
            raise ValueError("invalid inputs")
        envelope = json.loads(blob)
        if type(envelope) is not dict or set(envelope) != {"state", "mac"}:
            raise ValueError("invalid envelope")
        state = envelope["state"]
        if (type(state) is not dict or
                set(state) != {"format", "generation", "active", "keys", "retired"} or
                state["format"] != _FORMAT or
                type(state["generation"]) is not int or
                state["generation"] != expected_generation):
            raise ValueError("stale or malformed snapshot")
        raw = _canonical(state)
        if (type(envelope["mac"]) is not str or
                len(envelope["mac"]) != 44):
            raise ValueError("invalid signature")
        supplied = base64.b64decode(envelope["mac"], altchars=b"-_", validate=True)
        signed = hmac.new(secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied, signed):
            raise ValueError("bad signature")
        keydefs = state["keys"]
        retired = state["retired"]
        active = state["active"]
        if (type(keydefs) is not list or not 1 <= len(keydefs) <= 3
                or type(retired) is not list or
                type(active) is not str or
                not _KID.fullmatch(active)):
            raise ValueError("invalid key inventory")
        kids = []
        for definition in keydefs:
            if (type(definition) is not dict or
                    set(definition) != {"kid", "sha256"} or
                    type(definition["kid"]) is not str or
                    not _KID.fullmatch(definition["kid"]) or
                    type(definition["sha256"]) is not str or
                    not re.fullmatch(r"[0-9a-f]{64}", definition["sha256"])):
                raise ValueError("invalid key definition")
            kids.append(definition["kid"])
        if (len(set(kids)) != len(kids) or
                active not in kids or
                any(type(x) is not str or not _KID.fullmatch(x) for x in retired)
                or len(set(retired)) != len(retired) or set(kids) & set(retired)):
            raise ValueError("duplicate or retired key")
        # Require exactly the keys in the signed inventory: no hidden extras.
        if set(trusted_key_material) != set(kids):
            raise ValueError("untrusted or missing key material")
        for definition in keydefs:
            value = trusted_key_material[definition["kid"]]
            if (type(value) is not bytes or len(value) < 32 or
                    not hmac.compare_digest(hashlib.sha256(value).hexdigest(),
                                            definition["sha256"])):
                raise ValueError("key substitution")
        keys = {kid: PinnedAuditKey(kid, trusted_key_material[kid])
                for kid in kids}
        return AuditKeyringCandidate(
            active=keys[active],
            verify_only=tuple(keys[k] for k in kids if k != active),
            retired=tuple(retired),
            generation=expected_generation,
        )
    except Exception:
        raise FinanceAccessDenied("Finance audit key snapshot denied") from None
