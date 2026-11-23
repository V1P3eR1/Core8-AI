"""Read-only issue/comment scope evidence; NOT an independent Notion approval."""
import hashlib
import re
from github_provenance import EvidenceBlocked, REPO, positive

HEX64 = re.compile(r"^[a-f0-9]{64}$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
PREFIX = "https://api.github.com/repos/" + REPO + "/issues/"


def verify_issue_comment(issue, comment, *, issue_number, comment_id, approver_id,
                         task_uuid, task_digest, expected_issue_body_sha256):
    issue_number, comment_id, approver_id = (positive(x) for x in
                                           (issue_number, comment_id, approver_id))
    if not isinstance(task_uuid, str) or not UUID.fullmatch(task_uuid):
        raise EvidenceBlocked("invalid_task_uuid")
    if not isinstance(task_digest, str) or not HEX64.fullmatch(task_digest):
        raise EvidenceBlocked("invalid_task_digest")
    if not isinstance(expected_issue_body_sha256, str) or not HEX64.fullmatch(expected_issue_body_sha256):
        raise EvidenceBlocked("invalid_trusted_issue_hash")
    if not isinstance(issue, dict) or not isinstance(comment, dict):
        raise EvidenceBlocked("invalid_approval_metadata")
    body = issue.get("body")
    if (type(issue.get("number")) is not int or issue["number"] != issue_number
            or issue.get("state") != "open" or issue.get("pull_request") is not None
            or not isinstance(body, str) or len(body) > 100_000):
        raise EvidenceBlocked("issue_ineligible")
    if hashlib.sha256(body.encode("utf-8")).hexdigest() != expected_issue_body_sha256:
        raise EvidenceBlocked("issue_scope_changed")
    if body.count("<!-- core8-task:") != 1 or ("<!-- core8-task:" + task_uuid + " -->") not in body:
        raise EvidenceBlocked("task_marker_mismatch")
    if body.count("Scope SHA256:") != 1 or ("Scope SHA256: " + chr(96) + task_digest + chr(96)) not in body:
        raise EvidenceBlocked("scope_digest_mismatch")
    user = comment.get("user") or {}
    if (type(comment.get("id")) is not int or comment["id"] != comment_id
            or comment.get("issue_url") != PREFIX + str(issue_number)
            or comment.get("body") != "/core8-implement " + task_digest
            or comment.get("performed_via_github_app") not in (None, False)
            or not isinstance(comment.get("created_at"), str)
            or comment.get("updated_at") != comment["created_at"]
            or type(user.get("id")) is not int or user["id"] != approver_id
            or user.get("type") != "User"):
        raise EvidenceBlocked("approval_comment_mismatch")
    return {"repo": REPO, "issue_number": issue_number, "comment_id": comment_id,
            "approver_id": approver_id, "task_uuid": task_uuid,
            "task_digest": task_digest, "issue_body_sha256": expected_issue_body_sha256}


def fetch_verified_issue_comment(reader, *, issue_number, comment_id, approver_id,
                                 task_uuid, task_digest, expected_issue_body_sha256):
    issue_number, comment_id = positive(issue_number), positive(comment_id)
    issue = reader._get("issues/" + str(issue_number))
    comment = reader._get("issues/comments/" + str(comment_id))
    return verify_issue_comment(
        issue, comment, issue_number=issue_number, comment_id=comment_id,
        approver_id=approver_id, task_uuid=task_uuid, task_digest=task_digest,
        expected_issue_body_sha256=expected_issue_body_sha256)
