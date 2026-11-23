"""Signed audit keyring *metadata* snapshot; never serializes delivery secrets.

Sandbox-only, in-memory export/import. A real deployment needs a separately
administered durable anti-rollback floor and authenticated state storage. A
MAC-valid old snapshot is NOT safe to restore without the external generation.
The signing key for state metadata must be separate from delivery HMAC keys.
"""
import hashlib
import hmac
import json
import re

from audit_key_rotation_candidate import AuditKeyringCandidate, PinnedAuditKey
from tenant_access import FinanceAccessDenied

_FORMAT = "core8.finance.audit.keyring.v1"
_PREFIX = b"core8-audit-keyring-state-v1\x00"
_NS = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_MAX = 8192


def _auth_key(key):
    if type(key) is not bytes or len(key) < 32:
        raise FinanceAccessDenied("Finance audit state denied")
    return key


def _canonical(state):
    return json.dumps(
        state, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _key_proof(key, kid, secret):
    """Keyed secret fingerprint so a wrong provisioned secret fails restore."""
    return hmac.new(
        key, b"proof\x00" + kid.encode("ascii") + b"\x00" + secret,
        hashlib.sha256,
    ).hexdigest()


def export_audit_keyring_state(ring, *, namespace, state_signing_key):
    if (type(ring) is not AuditKeyringCandidate or
            type(namespace) is not str or not _NS.fullmatch(namespace)):
        raise FinanceAccessDenied("Finance audit state denied")
    key = _auth_key(state_signing_key)
    with ring._lock:
        state = {
            "format": _FORMAT,
            "namespace": namespace,
            "generation": ring.generation,
            "active": ring._active,
            "verify_only": sorted(k for k in ring._keys if k != ring._active),
            "retired": sorted(ring._retired),
            "proofs": {
                kid: _key_proof(key, kid, secret)
                for kid, secret in ring._keys.items()
            },
        }
        raw = _canonical(state)
    if len(raw) > _MAX:
        raise FinanceAccessDenied("Finance audit state denied")
    signature = hmac.new(key, _PREFIX + raw, hashlib.sha256).hexdigest()
    return _canonical({"state": state, "mac": signature})


def import_audit_keyring_state(blob, *, namespace, state_signing_key,
                               minimum_generation, pinned_secrets):
    """Recover only at an independently verified exact generation.

    pinned_secrets is trusted memory-only kid->secret provisioning, NOT the
    untrusted signed blob and never a client-controlled mapping.
    """
    try:
        key = _auth_key(state_signing_key)
        if (type(blob) is not bytes or len(blob) > _MAX
                or type(namespace) is not str or not _NS.fullmatch(namespace)
                or type(minimum_generation) is not int
                or minimum_generation < 1
                or type(pinned_secrets) is not dict):
            raise ValueError("invalid parameters")
        envelope = json.loads(blob)
        if type(envelope) is not dict or set(envelope) != {"state", "mac"}:
            raise ValueError("invalid envelope")
        state, tag = envelope["state"], envelope["mac"]
        if (type(state) is not dict or
                set(state) != {"format", "namespace", "generation", "active",
                               "verify_only", "retired", "proofs"}
                or type(tag) is not str or
                not re.fullmatch(r"[0-9a-f]{64}", tag)):
            raise ValueError("invalid shape")
        raw = _canonical(state)
        expected = hmac.new(key, _PREFIX + raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, tag):
            raise ValueError("invalid MAC")
        if (state["format"] != _FORMAT or state["namespace"] != namespace or
                type(state["generation"]) is not int or
                state["generation"] != minimum_generation or
                type(state["active"]) is not str or
                type(state["verify_only"]) is not list or
                type(state["retired"]) is not list or
                type(state["proofs"]) is not dict):
            raise ValueError("invalid state")
        active = state["active"]
        verify = state["verify_only"]
        retired = state["retired"]
        if (any(type(k) is not str for k in [active, *verify, *retired])
                or len(set([active, *verify, *retired]))
                != 1 + len(verify) + len(retired)
                or set(state["proofs"]) != {active, *verify}):
            raise ValueError("duplicate or stale kid")
        if set(pinned_secrets) != {active, *verify}:
            raise ValueError("unexpected trusted keyset")
        keys = []
        for kid in [active, *verify]:
            secret = pinned_secrets[kid]
            if type(secret) is not bytes or len(secret) < 32:
                raise ValueError("invalid trusted secret")
            proof = state["proofs"][kid]
            if (type(proof) is not str or
                    not hmac.compare_digest(_key_proof(key, kid, secret), proof)):
                raise ValueError("key mismatch")
            keys.append(PinnedAuditKey(kid, secret))
        return AuditKeyringCandidate(
            active=keys[0], verify_only=tuple(keys[1:]), retired=tuple(retired),
            generation=minimum_generation,
        )
    except Exception:
        raise FinanceAccessDenied("Finance audit state denied") from None
