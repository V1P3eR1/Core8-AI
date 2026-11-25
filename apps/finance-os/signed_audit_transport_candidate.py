"""Offline signed audit delivery boundary; NOT a live transport or IdP.

The trusted sender and receiver are separately provisioned with the same
sandbox-only secret. HMAC provides origin/integrity checks within this test
boundary but not public-key identity, secret storage, TLS or immutable storage.
No API and no outgoing network calls. Raw SQLiteAuditReceiverCandidate.accept
remains a test-only method and MUST NOT be exposed as a public ingress.
"""
import hashlib
import hmac
import json
import re

from tenant_access import FinanceAccessDenied

_NS = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_TAG = re.compile(r"^[0-9a-f]{64}$")
_PREFIX = b"core8-finance-audit-v1\x00"


def _payload_bytes(namespace, event_id, payload):
    try:
        if (type(namespace) is not str or not _NS.fullmatch(namespace)
                or type(event_id) is not str
                or type(payload) is not dict
                or payload.get("event_id") != event_id):
            raise ValueError("bad envelope")
        raw = json.dumps(
            [namespace, event_id, payload],
            sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        if len(raw) > 65536:
            raise ValueError("oversized envelope")
        return _PREFIX + raw
    except (TypeError, ValueError, UnicodeError, OverflowError):
        raise FinanceAccessDenied("Finance audit signature denied") from None


def _key(secret):
    if type(secret) is not bytes or len(secret) < 32:
        raise FinanceAccessDenied("Finance audit signature denied")
    return secret


def sign_audit_event(*, secret, namespace, event_id, payload):
    return hmac.new(
        _key(secret), _payload_bytes(namespace, event_id, payload),
        hashlib.sha256,
    ).hexdigest()


def verify_audit_event(*, secret, namespace, event_id, payload, signature):
    if type(signature) is not str or not _TAG.fullmatch(signature):
        raise FinanceAccessDenied("Finance audit signature denied")
    expected = sign_audit_event(
        secret=secret, namespace=namespace,
        event_id=event_id, payload=payload,
    )
    if not hmac.compare_digest(expected, signature):
        raise FinanceAccessDenied("Finance audit signature denied")


class SignedAuditReceiverCandidate:
    """Checked ingress for a preconfigured namespace; never accepts raw events."""

    def __init__(self, *, receiver, namespace, verification_key):
        _key(verification_key)
        if type(namespace) is not str or not _NS.fullmatch(namespace):
            raise FinanceAccessDenied("Finance audit signature denied")
        if receiver is None or not callable(getattr(receiver, "accept", None)):
            raise FinanceAccessDenied("Finance audit signature denied")
        self._receiver = receiver
        self._namespace = namespace
        self._key = verification_key

    def accept_signed(self, *, namespace, event_id, payload, signature):
        if namespace != self._namespace:
            raise FinanceAccessDenied("Finance audit signature denied")
        verify_audit_event(
            secret=self._key, namespace=namespace, event_id=event_id,
            payload=payload, signature=signature,
        )
        return self._receiver.accept(event_id, payload)


class SignedAuditSinkCandidate:
    """Sender adapter: signs the exact payload then calls local checked ingress."""

    def __init__(self, *, receiver, namespace, signing_key):
        _key(signing_key)
        if type(namespace) is not str or not _NS.fullmatch(namespace):
            raise FinanceAccessDenied("Finance audit signature denied")
        if receiver is None or not callable(getattr(receiver, "accept_signed", None)):
            raise FinanceAccessDenied("Finance audit signature denied")
        self._receiver = receiver
        self._namespace = namespace
        self._key = signing_key

    def accept(self, event_id, payload):
        signature = sign_audit_event(
            secret=self._key, namespace=self._namespace,
            event_id=event_id, payload=payload,
        )
        return self._receiver.accept_signed(
            namespace=self._namespace, event_id=event_id,
            payload=payload, signature=signature,
        )
