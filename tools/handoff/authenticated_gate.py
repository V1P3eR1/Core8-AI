"""Authenticate a protected-gate review receipt with separate verifier secret.

HMAC keys must come from independently controlled runner secrets, not repository
files, GitHub issues, Claude output, or user-supplied task metadata. This module
does not authorize publication, retrieve Notion, or expose the secret in errors.
"""
import hashlib
import hmac
import json
import re

from github_provenance import EvidenceBlocked

MAC = re.compile(r"^[0-9a-f]{64}$")
MAX_SIZE = 8192
DOMAIN = b"core8:protected-gate:review-only:v1\x00"


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceBlocked("gate_duplicate_json_key")
        result[key] = value
    return result


def verify_gate_receipt(raw, signature, *, verifier_key):
    """Verify raw canonical UTF-8 JSON bytes before yielding the gate object.

    The caller must independently authenticate which protected job produced
    this receipt and bind its key to that job. Only the strict payload is
    returned, and its authorizing effect is always review-only.
    """
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_SIZE:
        raise EvidenceBlocked("invalid_signed_gate_bytes")
    if not isinstance(verifier_key, bytes) or len(verifier_key) < 32:
        raise EvidenceBlocked("missing_protected_gate_key")
    if not isinstance(signature, str) or not MAC.fullmatch(signature):
        raise EvidenceBlocked("invalid_gate_signature")
    expected = hmac.new(verifier_key, DOMAIN + raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise EvidenceBlocked("gate_signature_mismatch")
    try:
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except EvidenceBlocked:
        raise
    except (UnicodeDecodeError, ValueError):
        raise EvidenceBlocked("invalid_signed_gate_json") from None
    if not isinstance(record, dict):
        raise EvidenceBlocked("invalid_signed_gate_schema")
    # One canonical representation prevents semantic ambiguity between tools.
    canonical = json.dumps(record, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")
    if canonical != raw:
        raise EvidenceBlocked("noncanonical_signed_gate_json")
    return record


def bind_signed_review_evidence(approval, run_artifact, raw, signature, *,
                                verifier_key, now):
    """Fail closed on signature before comparing the protected run binding."""
    from evidence_binding import bind_review_evidence

    protected = verify_gate_receipt(raw, signature, verifier_key=verifier_key)
    return bind_review_evidence(approval, run_artifact, protected, now=now)
