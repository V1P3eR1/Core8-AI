"""Sandbox-only HMAC key rotation policy for signed audit delivery.

A verified/authorized operator must supply a pinned keyset. This module does
NOT load or persist secrets, authenticate an operator, or provide KMS/HSM.
Keysets must be pinned by trusted configuration, never request headers.
"""
from dataclasses import dataclass
import hashlib
import hmac
import re
from threading import RLock

from signed_audit_transport_candidate import _payload_bytes
from tenant_access import FinanceAccessDenied

_KID = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_TAG = re.compile(r"^[0-9a-f]{64}$")
_PREFIX = b"core8-finance-audit-rotation-v1\x00"


def _validate_kid(kid):
    if type(kid) is not str or not _KID.fullmatch(kid):
        raise FinanceAccessDenied("Finance audit key denied")


def _validate_secret(secret):
    if type(secret) is not bytes or len(secret) < 32:
        raise FinanceAccessDenied("Finance audit key denied")


@dataclass(frozen=True)
class PinnedAuditKey:
    kid: str
    secret: bytes


class AuditKeyringCandidate:
    """One active signer, optional retired-from-signing verification keys.

    Verification keys retain explicit trust while rotation overlaps. A key
    removal permanently tombstones the kid within this instance and cannot
    be reactivated, even with identical key material. On process restart
    production must restore a trusted, separately authenticated tombstone
    snapshot and anti-rollback watermark. This candidate has no persistence.
    """

    def __init__(self, *, active, verify_only=(), retired=(), generation=1):
        if type(generation) is not int or generation < 1:
            raise FinanceAccessDenied("Finance audit key denied")
        if type(active) is not PinnedAuditKey or type(verify_only) not in (tuple, list):
            raise FinanceAccessDenied("Finance audit key denied")
        if type(retired) not in (tuple, list, frozenset):
            raise FinanceAccessDenied("Finance audit key denied")
        keys = [active, *verify_only]
        if len(keys) > 3:
            raise FinanceAccessDenied("Finance audit key denied")
        by_kid = {}
        for key in keys:
            if type(key) is not PinnedAuditKey:
                raise FinanceAccessDenied("Finance audit key denied")
            _validate_kid(key.kid)
            _validate_secret(key.secret)
            if key.kid in by_kid:
                raise FinanceAccessDenied("Finance audit key denied")
            by_kid[key.kid] = key.secret
        tombstones = set(retired)
        if any(type(x) is not str or not _KID.fullmatch(x) for x in tombstones):
            raise FinanceAccessDenied("Finance audit key denied")
        if tombstones.intersection(by_kid):
            raise FinanceAccessDenied("Finance audit key denied")
        self._lock = RLock()
        self._active = active.kid
        self._keys = by_kid
        self._retired = tombstones
        self.generation = generation

    @property
    def active_kid(self):
        with self._lock:
            return self._active

    def sign(self, *, namespace, event_id, payload):
        with self._lock:
            key = self._keys[self._active]
            raw = _PREFIX + self._active.encode("ascii") + b"\x00"
            raw += _payload_bytes(namespace, event_id, payload)
            return (self._active, hmac.new(key, raw, hashlib.sha256).hexdigest())

    def verify(self, *, namespace, event_id, payload, kid, signature):
        with self._lock:
            _validate_kid(kid)
            if type(signature) is not str or not _TAG.fullmatch(signature):
                raise FinanceAccessDenied("Finance audit signature denied")
            key = self._keys.get(kid)
            if key is None:
                raise FinanceAccessDenied("Finance audit signature denied")
            raw = _PREFIX + kid.encode("ascii") + b"\x00"
            raw += _payload_bytes(namespace, event_id, payload)
            expected = hmac.new(key, raw, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise FinanceAccessDenied("Finance audit signature denied")

    def rotate(self, *, expected_generation, new_active, retain=()):
        """Atomic-in-memory transition; never replace key material for a kid."""
        with self._lock:

            if (type(expected_generation) is not int or
                    expected_generation != self.generation or
                    type(new_active) is not PinnedAuditKey or
                    type(retain) not in (list, tuple, frozenset)):
                raise FinanceAccessDenied("Finance audit key denied")
            _validate_kid(new_active.kid)
            _validate_secret(new_active.secret)
            remaining = set(retain)
            if (len(remaining) != len(retain) or
                    any(type(x) is not str or x not in self._keys
                        for x in remaining)):
                raise FinanceAccessDenied("Finance audit key denied")
            if new_active.kid in self._retired:
                raise FinanceAccessDenied("Finance audit key denied")
            prior = self._keys.get(new_active.kid)
            if prior is not None and not hmac.compare_digest(prior, new_active.secret):
                raise FinanceAccessDenied("Finance audit key denied")
            chosen = {k: self._keys[k] for k in remaining}
            chosen[new_active.kid] = new_active.secret
            if len(chosen) > 3:
                raise FinanceAccessDenied("Finance audit key denied")
            # Do not permit any key not explicitly retained to reappear.
            new_retired = self._retired | (set(self._keys) - set(chosen))
            self._keys = chosen
            self._retired = new_retired
            self._active = new_active.kid
            self.generation += 1
            return self.generation


class RotatingAuditReceiverCandidate:
    """An authenticated in-process adapter to an existing disposable sink."""

    def __init__(self, *, receiver, namespace, keyring):
        if type(keyring) is not AuditKeyringCandidate or not hasattr(receiver, "accept"):
            raise FinanceAccessDenied("Finance audit key denied")
        self._receiver = receiver
        self._namespace = namespace
        self._keyring = keyring

    def accept_signed(self, *, namespace, event_id, payload, kid, signature):
        if namespace != self._namespace:
            raise FinanceAccessDenied("Finance audit signature denied")
        self._keyring.verify(
            namespace=namespace, event_id=event_id, payload=payload,
            kid=kid, signature=signature,
        )
        return self._receiver.accept(event_id, payload)


class RotatingAuditSinkCandidate:
    """Local-only sender adapter with key ID bound into the MAC."""

    def __init__(self, *, receiver, namespace, keyring):
        if type(keyring) is not AuditKeyringCandidate or not hasattr(receiver, "accept_signed"):
            raise FinanceAccessDenied("Finance audit key denied")
        self._receiver = receiver
        self._namespace = namespace
        self._keyring = keyring

    def accept(self, event_id, payload):
        kid, signature = self._keyring.sign(
            namespace=self._namespace, event_id=event_id, payload=payload,
        )
        return self._receiver.accept_signed(
            namespace=self._namespace, event_id=event_id,
            payload=payload, kid=kid, signature=signature,
        )
