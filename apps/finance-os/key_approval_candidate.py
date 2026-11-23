"""Review-only two-person approval gate for JWKS rotations.

This is an UNWIRED policy adapter, NOT authentication or a durable approval
ledger. Operators and approvals must originate from independently authenticated,
server-maintained records. Never construct them from request/JWT role claims.
Only trusted operator workflow should invoke authorize_and_rotate.
"""
from dataclasses import dataclass
import hashlib
import json
import re
import time

from tenant_access import FinanceAccessDenied

_OPERATOR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_:.@|-]{2,199}$")
_NAMESPACE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_APPROVAL_ID = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_ALLOWED_ROLES = frozenset({"key_manager", "security_approver"})


@dataclass(frozen=True)
class ServerVerifiedOperator:
    subject: str
    role: str
    enabled: bool = True


@dataclass(frozen=True)
class StoredKeyApproval:
    approval_id: str
    requester_subject: str
    approver_subject: str
    proposal_sha256: str
    expires_at: int


class IndependentApprovalLedger:
    """A trusted, durable consume-once service must implement this contract.

    consume must atomically verify the supplied approval and mark it used;
    the caller MUST NOT be able to forge or self-issue approval records.
    """

    def consume(self, approval_id, expected):
        raise NotImplementedError


def proposal_hash(*, namespace, expected_generation, proposed_jwks, retire):
    """Canonical digest binds approval to namespace + exact rotation content."""
    try:
        if (type(namespace) is not str or not _NAMESPACE.fullmatch(namespace)
                or type(expected_generation) is not int or expected_generation < 1
                or type(proposed_jwks) is not dict
                or type(retire) not in (tuple, list, frozenset)
                or any(type(x) is not str for x in retire)):
            raise ValueError("invalid proposal")
        if len(set(retire)) != len(retire):
            raise ValueError("duplicate retired key")
        envelope = {
            "namespace": namespace,
            "expected_generation": expected_generation,
            "jwks": proposed_jwks,
            "retire": sorted(retire),
        }
        raw = json.dumps(envelope, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
        if len(raw) > 65536:
            raise ValueError("large proposal")
        return hashlib.sha256(raw).hexdigest()
    except Exception:
        raise FinanceAccessDenied("Finance key approval denied") from None


def require_key_approval(*, requester, approver, approval, namespace,
                         expected_generation, proposed_jwks, retire=(),
                         now=None):
    """Check two independently authenticated identities and stored approval."""
    if (type(requester) is not ServerVerifiedOperator
            or type(approver) is not ServerVerifiedOperator
            or type(approval) is not StoredKeyApproval):
        raise FinanceAccessDenied("Finance key approval denied")
    for identity in (requester, approver):
        if (type(identity.subject) is not str or not _OPERATOR.fullmatch(identity.subject)
                or type(identity.enabled) is not bool or not identity.enabled
                or identity.role not in _ALLOWED_ROLES):
            raise FinanceAccessDenied("Finance key approval denied")
    if (requester.role != "key_manager"
            or approver.role != "security_approver"
            or requester.subject == approver.subject
            or approval.requester_subject != requester.subject
            or approval.approver_subject != approver.subject
            or type(approval.approval_id) is not str
            or not _APPROVAL_ID.fullmatch(approval.approval_id)):
        raise FinanceAccessDenied("Finance key approval denied")
    instant = int(time.time()) if now is None else now
    if (type(instant) is not int or type(approval.expires_at) is not int
            or approval.expires_at <= instant
            or approval.expires_at > instant + 900):
        raise FinanceAccessDenied("Finance key approval denied")
    fingerprint = proposal_hash(
        namespace=namespace, expected_generation=expected_generation,
        proposed_jwks=proposed_jwks, retire=retire,
    )
    if approval.proposal_sha256 != fingerprint:
        raise FinanceAccessDenied("Finance key approval denied")


def authorize_and_rotate(*, ledger, requester, approver, approval, conn,
                         namespace, signing_key, floor, expected_generation,
                         proposed_jwks, retire=(), now=None):
    """Consume approval before attempting rotation, failing closed.

    Even if DB/CAS later fails, the approval is consumed; a new approval is
    required for any retry. This deliberately prefers safety over availability.
    """
    if not isinstance(ledger, IndependentApprovalLedger):
        raise FinanceAccessDenied("Finance key approval denied")
    require_key_approval(
        requester=requester, approver=approver, approval=approval,
        namespace=namespace, expected_generation=expected_generation,
        proposed_jwks=proposed_jwks, retire=retire, now=now,
    )
    try:
        consumed = ledger.consume(approval.approval_id, approval)
    except Exception:
        raise FinanceAccessDenied("Finance key approval denied") from None
    if consumed is not True:
        raise FinanceAccessDenied("Finance key approval denied")
    from external_floor_candidate import rotate_with_external_floor
    return rotate_with_external_floor(
        conn, namespace=namespace, signing_key=signing_key, floor=floor,
        expected_generation=expected_generation, proposed_jwks=proposed_jwks,
        retire=retire,
    )
