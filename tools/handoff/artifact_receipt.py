"""Pure validation for trusted job metadata before Claude patch review.

Caller MUST obtain both arguments from separately authenticated/authorized sources.
A caller copying untrusted artifact metadata into expected_record defeats this check.
No network, filesystem modifications, credential access, or artifact publication.
"""
import hashlib
import re
from datetime import datetime, timezone

REPO = "V1P3eR1/Core8-AI"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
MAX_AGE_SECONDS = 7 * 24 * 3600
MAX_PATCH_BYTES = 256 * 1024


class RejectedArtifact(ValueError):
    """A fixed rejection code, never an external response body."""


def _time(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RejectedArtifact("invalid_timestamp")
    try:
        timestamp = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise RejectedArtifact("invalid_timestamp") from None
    return timestamp


def validate_artifact_receipt(*, receipt, expected_record, patch_bytes, now, consumed):
    """Validate a metadata receipt against an independently trusted task/run record.

    This does not cryptographically authenticate GitHub, and does not apply the patch.
    Caller must fetch run/artifact metadata using an authorized GitHub API connection,
    check task approval separately, and atomically record consumption after acceptance.
    """
    if not isinstance(receipt, dict) or not isinstance(expected_record, dict):
        raise RejectedArtifact("invalid_metadata")
    if not isinstance(consumed, (set, frozenset)):
        raise RejectedArtifact("invalid_consumption_registry")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise RejectedArtifact("invalid_clock")
    now = now.astimezone(timezone.utc)
    if not isinstance(patch_bytes, bytes) or not patch_bytes or len(patch_bytes) > MAX_PATCH_BYTES:
        raise RejectedArtifact("invalid_artifact_size")
    for field in ("repo", "run_id", "artifact_id", "head_sha", "task_digest",
                  "task_revision", "issue_number", "approver_id", "run_event"):
        if field not in receipt or field not in expected_record:
            raise RejectedArtifact("missing_metadata")
        if receipt[field] != expected_record[field]:
            raise RejectedArtifact("provenance_mismatch")
    # Cross-check claims against separately authenticated GitHub metadata.
    for field in ("run_conclusion", "artifact_name", "expired", "artifact_sha256",
                  "created_at", "expires_at"):
        if field not in receipt or field not in expected_record:
            raise RejectedArtifact("missing_metadata")
        if receipt[field] != expected_record[field]:
            raise RejectedArtifact("provenance_mismatch")
    if receipt["repo"] != REPO or receipt["run_event"] != "issue_comment":
        raise RejectedArtifact("untrusted_origin")
    for field in ("run_id", "artifact_id", "task_revision", "issue_number", "approver_id"):
        if type(receipt[field]) is not int or receipt[field] <= 0:
            raise RejectedArtifact("invalid_identifier")
    if not isinstance(receipt["head_sha"], str) or not SHA40.fullmatch(receipt["head_sha"]):
        raise RejectedArtifact("invalid_commit")
    if not isinstance(receipt["task_digest"], str) or not SHA256.fullmatch(receipt["task_digest"]):
        raise RejectedArtifact("invalid_task_digest")
    if expected_record.get("decision") != "Approved" or expected_record.get("public_export") is not True:
        raise RejectedArtifact("not_approved")
    if expected_record.get("execution_authorized") is not True:
        raise RejectedArtifact("execution_not_authorized")
    if receipt.get("run_conclusion") != "success":
        raise RejectedArtifact("run_not_successful")
    if receipt.get("artifact_name") != "core8-implementation-patch":
        raise RejectedArtifact("unexpected_artifact")
    if receipt.get("expired") is not False:
        raise RejectedArtifact("artifact_expired")
    digest = receipt.get("artifact_sha256")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise RejectedArtifact("invalid_artifact_digest")
    if hashlib.sha256(patch_bytes).hexdigest() != digest:
        raise RejectedArtifact("artifact_digest_mismatch")
    started, expires = _time(receipt.get("created_at")), _time(receipt.get("expires_at"))
    if started > now or expires <= now or expires <= started or (now - started).total_seconds() > MAX_AGE_SECONDS:
        raise RejectedArtifact("artifact_outside_window")
    key = (receipt["repo"], receipt["run_id"], receipt["artifact_id"])
    if key in consumed:
        raise RejectedArtifact("already_consumed")
    return {"artifact_key": key, "sha256": digest, "issue_number": receipt["issue_number"],
            "head_sha": receipt["head_sha"], "task_revision": receipt["task_revision"]}
