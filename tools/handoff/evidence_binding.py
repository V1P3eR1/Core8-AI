"""Fail-closed binding of independently verified approval and Actions evidence.

The trusted gate is independently authenticated as protected run output.
Never construct it from Claude artifacts, task text or issue comments.
"""
import re
from datetime import datetime, timezone
from github_provenance import EvidenceBlocked, REPO, positive

HEX40 = re.compile(r"^[a-f0-9]{40}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")


def utc_time(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise EvidenceBlocked("invalid_provenance_time")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise EvidenceBlocked("invalid_provenance_time") from None
    if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
        raise EvidenceBlocked("invalid_provenance_time")
    return result


def bind_review_evidence(approval, run_artifact, protected_gate, *, now):
    """Check exact trusted binding; this does NOT authorize any publishing.

    Caller must authenticate protected_gate externally; this function cannot
    authenticate an arbitrary Python dict. Missing gate always blocks.
    """
    if not isinstance(approval, dict) or not isinstance(run_artifact, dict):
        raise EvidenceBlocked("missing_verified_evidence")
    if not isinstance(protected_gate, dict):
        raise EvidenceBlocked("missing_protected_gate")
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise EvidenceBlocked("invalid_current_time")
    now = now.astimezone(timezone.utc)
    required = {"repo", "run_id", "artifact_id", "comment_id", "issue_number",
                "approver_id", "task_uuid", "task_digest", "head_sha",
                "issue_body_sha256", "task_revision", "approved_at"}
    if set(protected_gate) != required:
        raise EvidenceBlocked("invalid_gate_schema")
    for name in ("run_id", "artifact_id", "comment_id", "issue_number",
                 "approver_id", "task_revision"):
        positive(protected_gate[name])
    if protected_gate["repo"] != REPO:
        raise EvidenceBlocked("gate_repo_mismatch")
    if not isinstance(protected_gate["head_sha"], str) or not HEX40.fullmatch(protected_gate["head_sha"]):
        raise EvidenceBlocked("invalid_gate_head")
    for name in ("task_digest", "issue_body_sha256"):
        value = protected_gate[name]
        if not isinstance(value, str) or not HEX64.fullmatch(value):
            raise EvidenceBlocked("invalid_gate_hash")
    approval_fields = ("repo", "comment_id", "issue_number", "approver_id",
                       "task_uuid", "task_digest", "issue_body_sha256")
    run_fields = ("repo", "run_id", "artifact_id", "approver_id", "head_sha")
    if any(approval.get(key) != protected_gate[key] for key in approval_fields):
        raise EvidenceBlocked("approval_gate_mismatch")
    if any(run_artifact.get(key) != protected_gate[key] for key in run_fields):
        raise EvidenceBlocked("run_gate_mismatch")
    if (run_artifact.get("run_conclusion") != "success"
            or run_artifact.get("run_event") != "issue_comment"
            or run_artifact.get("expired") is not False):
        raise EvidenceBlocked("run_not_eligible")
    archive_hash = run_artifact.get("archive_sha256")
    if not isinstance(archive_hash, str) or not HEX64.fullmatch(archive_hash):
        raise EvidenceBlocked("invalid_archive_digest")
    approved = utc_time(protected_gate["approved_at"])
    created = utc_time(run_artifact.get("created_at"))
    expires = utc_time(run_artifact.get("expires_at"))
    if not (approved <= created <= now < expires):
        raise EvidenceBlocked("approval_or_artifact_time_mismatch")
    return {
        "status": "BOUND_FOR_REVIEW_ONLY", "repo": REPO,
        "run_id": protected_gate["run_id"],
        "artifact_id": protected_gate["artifact_id"],
        "comment_id": protected_gate["comment_id"],
        "issue_number": protected_gate["issue_number"],
        "approver_id": protected_gate["approver_id"],
        "task_uuid": protected_gate["task_uuid"],
        "task_digest": protected_gate["task_digest"],
        "task_revision": protected_gate["task_revision"],
        "head_sha": protected_gate["head_sha"],
        "archive_sha256": archive_hash,
    }
