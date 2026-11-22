"""Read-only GitHub Actions metadata gate for a Core8 Claude patch artifact.

No artifact downloads, Notion access, patch execution or GitHub writes.
Approval/issue binding MUST be verified independently against the existing
protected Notion/GitHub human gate; API metadata alone does not prove it.
"""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

REPO = "V1P3eR1/Core8-AI"
REPO_ID = 1400042928
ARTIFACT_NAME = "core8-implementation-patch"
WORKFLOW_PATH = ".github/workflows/claude-issues.yml"
HEX40 = re.compile(r"^[a-f0-9]{40}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")
MAX_REPLY = 150_000


class EvidenceBlocked(ValueError):
    """A fixed error code, with no provider response bodies or token contents."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def positive(value):
    if type(value) is not int or value <= 0:
        raise EvidenceBlocked("invalid_id")
    return value


def validate_run_artifact(run, artifact, *, run_id, artifact_id, head_sha):
    """Check two authenticated GitHub API objects against exact immutable IDs.

    These objects MUST be obtained independently from GitHub using an authorized
    read-only connection, not from task text or Claude output.
    """
    run_id, artifact_id = positive(run_id), positive(artifact_id)
    if not isinstance(head_sha, str) or not HEX40.fullmatch(head_sha):
        raise EvidenceBlocked("invalid_head_sha")
    if not isinstance(run, dict) or not isinstance(artifact, dict):
        raise EvidenceBlocked("invalid_response")
    rrepo = run.get("repository") or {}
    if not (run.get("id") == run_id and type(run.get("id")) is int
            and rrepo.get("full_name") == REPO and rrepo.get("id") == REPO_ID
            and run.get("event") == "issue_comment"
            and run.get("head_branch") == "main"
            and run.get("head_sha") == head_sha
            and run.get("path") == WORKFLOW_PATH
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
            and run.get("run_attempt") == 1):
        raise EvidenceBlocked("run_mismatch")
    linked = artifact.get("workflow_run") or {}
    if not (artifact.get("id") == artifact_id
            and type(artifact.get("id")) is int
            and artifact.get("name") == ARTIFACT_NAME
            and artifact.get("expired") is False
            and linked.get("id") == run_id
            and linked.get("head_sha") == head_sha
            and linked.get("head_branch") == "main"
            and linked.get("repository_id") == REPO_ID):
        raise EvidenceBlocked("artifact_mismatch")
    digest = artifact.get("digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:") or not HEX64.fullmatch(digest[7:]):
        raise EvidenceBlocked("missing_trusted_artifact_digest")
    created, expires = artifact.get("created_at"), artifact.get("expires_at")
    for value in (created, expires):
        if not isinstance(value, str) or not value.endswith("Z") or len(value) > 40:
            raise EvidenceBlocked("invalid_artifact_time")
    return {
        "repo": REPO, "run_id": run_id, "artifact_id": artifact_id,
        "head_sha": head_sha, "run_event": "issue_comment",
        "run_conclusion": "success", "artifact_name": ARTIFACT_NAME,
        "expired": False, "artifact_sha256": digest[7:],
        "created_at": created, "expires_at": expires,
    }


class GitHubReadOnly:
    """Narrow GitHub GET-only client; does not follow HTTP redirects."""

    def __init__(self, token, opener=None):
        if not isinstance(token, str) or not token:
            raise EvidenceBlocked("missing_credentials")
        self._token = token
        self._opener = opener or build_opener(NoRedirect())

    def _get(self, resource):
        url = "https://api.github.com/repos/" + REPO + "/" + resource
        request = Request(url, headers={
            "Authorization": "Bearer " + self._token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "core8-read-only-provenance",
        }, method="GET")
        try:
            with self._opener.open(request, timeout=15) as response:
                payload = response.read(MAX_REPLY + 1)
        except (HTTPError, URLError, TimeoutError, OSError):
            raise EvidenceBlocked("github_fetch_failed") from None
        if len(payload) > MAX_REPLY:
            raise EvidenceBlocked("github_response_too_large")
        try:
            doc = json.loads(payload)
        except (UnicodeDecodeError, ValueError):
            raise EvidenceBlocked("github_response_invalid") from None
        if not isinstance(doc, dict):
            raise EvidenceBlocked("github_response_invalid")
        return doc

    def fetch_verified(self, *, run_id, artifact_id, head_sha):
        run_id, artifact_id = positive(run_id), positive(artifact_id)
        run = self._get("actions/runs/" + str(run_id))
        artifact = self._get("actions/artifacts/" + str(artifact_id))
        return validate_run_artifact(run, artifact, run_id=run_id,
                                     artifact_id=artifact_id, head_sha=head_sha)
