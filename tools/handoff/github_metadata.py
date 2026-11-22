"""Read-only GitHub metadata source for an already human-approved Claude run.

This does NOT authenticate current Notion decisions or start Claude. An external
trusted gate must independently verify scope approval, current task revision,
human approver identity and consumed-artifact state before any publication.
"""
from datetime import datetime
import json
import re
from urllib import request

REPO = "V1P3eR1/Core8-AI"
API = "https://api.github.com/repos/" + REPO + "/"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
MAX_JSON_BYTES = 64_000
MAX_ZIP_BYTES = 2 * 1024 * 1024
WORKFLOW_NAME = "Core8 approved Claude patch"


class MetadataRejected(ValueError):
    pass


class _NoRedirect(request.HTTPRedirectHandler):
    """Do not follow redirects while an API bearer token is attached."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise MetadataRejected("github_redirect_refused")


def _timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise MetadataRejected("invalid_timestamp")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MetadataRejected("invalid_timestamp") from exc


def github_readonly_get(endpoint, token):
    if not isinstance(token, str) or not token:
        raise MetadataRejected("authenticated_read_token_required")
    if not re.fullmatch(r"[A-Za-z0-9/]+", endpoint):
        raise MetadataRejected("invalid_api_path")
    url = API + endpoint
    req = request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }, method="GET")
    try:
        with request.build_opener(_NoRedirect).open(req, timeout=12) as response:
            if response.geturl() != url:
                raise MetadataRejected("unexpected_api_redirect")
            raw = response.read(MAX_JSON_BYTES + 1)
    except MetadataRejected:
        raise
    except Exception as exc:
        raise MetadataRejected("github_read_failed") from exc
    if len(raw) > MAX_JSON_BYTES:
        raise MetadataRejected("oversized_api_response")
    try:
        obj = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise MetadataRejected("invalid_api_json") from exc
    if not isinstance(obj, dict):
        raise MetadataRejected("invalid_api_object")
    return obj


def validate_github_metadata(*, run_id, artifact_id, comment_id, token, get=github_readonly_get):
    """All three HTTP responses MUST come from authenticated GitHub endpoints."""
    if any(type(i) is not int or i <= 0 for i in (run_id, artifact_id, comment_id)):
        raise MetadataRejected("invalid_identifiers")
    run = get("actions/runs/" + str(run_id), token)
    artifact = get("actions/artifacts/" + str(artifact_id), token)
    comment = get("issues/comments/" + str(comment_id), token)
    if run.get("id") != run_id or run.get("event") != "issue_comment":
        raise MetadataRejected("wrong_run")
    if run.get("name") != WORKFLOW_NAME or run.get("status") != "completed" or run.get("conclusion") != "success":
        raise MetadataRejected("wrong_workflow_or_result")
    if run.get("repository", {}).get("full_name") != REPO:
        raise MetadataRejected("wrong_repository")
    sha = run.get("head_sha")
    if not isinstance(sha, str) or not SHA40.fullmatch(sha):
        raise MetadataRejected("invalid_head_sha")
    if artifact.get("id") != artifact_id or artifact.get("name") != "core8-implementation-patch":
        raise MetadataRejected("wrong_artifact")
    if artifact.get("workflow_run", {}).get("id") != run_id:
        raise MetadataRejected("artifact_run_mismatch")
    if artifact.get("expired") is not False:
        raise MetadataRejected("expired_artifact")
    size = artifact.get("size_in_bytes")
    if type(size) is not int or not 0 < size <= MAX_ZIP_BYTES:
        raise MetadataRejected("artifact_size")
    digest = artifact.get("digest")
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise MetadataRejected("missing_github_zip_digest")
    if comment.get("id") != comment_id:
        raise MetadataRejected("wrong_comment")
    issue_url = comment.get("issue_url")
    prefix = API + "issues/"
    if not isinstance(issue_url, str) or not issue_url.startswith(prefix):
        raise MetadataRejected("wrong_issue_url")
    suffix = issue_url[len(prefix):]
    if not re.fullmatch(r"[1-9][0-9]*", suffix):
        raise MetadataRejected("wrong_issue_number")
    actor_id = run.get("actor", {}).get("id")
    approver_id = comment.get("user", {}).get("id")
    if type(actor_id) is not int or actor_id <= 0 or actor_id != approver_id:
        raise MetadataRejected("unrelated_approval_comment")
    body = comment.get("body")
    if not isinstance(body, str):
        raise MetadataRejected("missing_approval_comment")
    match = re.fullmatch(r"/core8-implement ([0-9a-f]{64})", body.strip())
    if not match:
        raise MetadataRejected("not_a_hash_approval")
    created = _timestamp(artifact.get("created_at"))
    expires = _timestamp(artifact.get("expires_at"))
    run_created = _timestamp(run.get("created_at"))
    approval_created = _timestamp(comment.get("created_at"))
    if expires <= created or run_created < approval_created:
        raise MetadataRejected("invalid_provenance_time")
    if (run_created - approval_created).total_seconds() > 86400:
        raise MetadataRejected("approval_outside_run_window")
    return {
        "repo": REPO, "run_id": run_id, "artifact_id": artifact_id,
        "issue_number": int(suffix), "approver_id": approver_id,
        "approval_comment_id": comment_id,
        "task_digest": match.group(1), "head_sha": sha,
        "run_event": "issue_comment", "run_conclusion": "success",
        "artifact_name": "core8-implementation-patch",
        "archive_digest": digest,
        "created_at": artifact["created_at"],
        "expires_at": artifact["expires_at"],
    }
