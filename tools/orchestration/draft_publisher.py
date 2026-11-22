#!/usr/bin/env python3
"""Draft-only GitHub writer for an independently validated Claude artifact bundle.

NOT an approval gate. Must run only in a separately protected, authorized writer
job, never in the untrusted patch-processing job. Dry-run by default.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import sys
from urllib import request, error, parse
from patch_gate import _check_path, PatchRejected

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
MAX_BUNDLE = 2_000_000
MAX_FILES = 20
MAX_FILE = 100_000


class PublishBlocked(ValueError):
    pass


class HttpFailed(Exception):
    def __init__(self, status):
        self.status = status
        super().__init__(f"github_status_{status}")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect_bundle(raw, expected_bundle_sha, *, base_sha, scope_sha, artifact_sha):
    if len(raw) > MAX_BUNDLE or not raw or not SHA256.fullmatch(expected_bundle_sha):
        raise PublishBlocked("invalid_bundle")
    if digest(raw) != expected_bundle_sha:
        raise PublishBlocked("bundle_digest_mismatch")
    if not SHA40.fullmatch(base_sha) or any(not SHA256.fullmatch(x) for x in (scope_sha, artifact_sha)):
        raise PublishBlocked("invalid_trusted_metadata")
    try:
        obj = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise PublishBlocked("bad_json") from exc
    if not isinstance(obj, dict) or obj.get("schema") != 1 or obj.get("status") != "REVIEW_ONLY":
        raise PublishBlocked("invalid_schema")
    if (obj.get("base_sha"), obj.get("approved_scope_sha256"), obj.get("artifact_sha256")) != (base_sha, scope_sha, artifact_sha):
        raise PublishBlocked("scope_or_base_mismatch")
    idem = digest((base_sha + ":" + artifact_sha + ":" + scope_sha).encode())
    if obj.get("idempotency_key") != idem:
        raise PublishBlocked("idempotency_mismatch")
    files = obj.get("files")
    if not isinstance(files, list) or not 0 < len(files) <= MAX_FILES:
        raise PublishBlocked("file_count")
    paths = []
    verified_files = []
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "content_b64"}:
            raise PublishBlocked("bad_file_record")
        path = entry["path"]
        if not isinstance(path, str):
            raise PublishBlocked("bad_path")
        try:
            _check_path(path)
        except PatchRejected as exc:
            raise PublishBlocked("forbidden_path") from exc
        h = entry["sha256"]
        if not isinstance(h, str) or not SHA256.fullmatch(h):
            raise PublishBlocked("bad_file_hash")
        try:
            content = base64.b64decode(entry["content_b64"], validate=True)
        except (ValueError, TypeError) as exc:
            raise PublishBlocked("bad_file_data") from exc
        if len(content) > MAX_FILE or digest(content) != h or b"\x00" in content:
            raise PublishBlocked("file_data_mismatch_or_binary")
        if re.search(rb"(?:sk-ant-|sk-proj-|ghp_|github_pat_|ntn_)[A-Za-z0-9_-]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY-----", content):
            raise PublishBlocked("possible_secret")
        paths.append(path)
        verified_files.append((path, base64.b64encode(content).decode()))
    if len(paths) != len(set(paths)) or sorted(paths) != obj.get("paths"):
        raise PublishBlocked("path_list_mismatch")
    return idem, verified_files


class GitHubApi:
    def __init__(self, repo, token):
        if not REPO.fullmatch(repo):
            raise PublishBlocked("invalid_repository")
        self.repo = repo
        self.token = token

    def call(self, method, path, payload=None):
        url = f"https://api.github.com/repos/{self.repo}/{path}"
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Authorization": "Bearer " + self.token,
                   "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = request.Request(url, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=15) as response:
                return json.loads(response.read())
        except error.HTTPError as exc:
            raise HttpFailed(exc.code) from None


def publish(api, *, repo, base_sha, bundle_raw, bundle_hash, scope_sha, artifact_sha):
    if not REPO.fullmatch(repo) or api.repo != repo:
        raise PublishBlocked("repository_mismatch")
    idem, files = inspect_bundle(bundle_raw, bundle_hash, base_sha=base_sha, scope_sha=scope_sha, artifact_sha=artifact_sha)
    branch = "core8-review/" + idem[:24]
    head = repo.split("/")[0] + ":" + branch
    marker = "<!-- core8-review:" + idem + " -->"
    query = parse.urlencode({"head": head, "base": "main", "state": "open"})
    existing = api.call("GET", "pulls?" + query)
    if existing:
        if (len(existing) == 1 and existing[0].get("draft") is True
                and marker in (existing[0].get("body") or "")):
            return {"status": "EXISTING_DRAFT", "url": existing[0]["html_url"], "branch": branch}
        raise PublishBlocked("conflicting_existing_pr")
    ref_path = "git/ref/heads/" + parse.quote(branch, safe="")
    try:
        api.call("GET", ref_path)
    except HttpFailed as exc:
        if exc.status != 404:
            raise
    else:
        raise PublishBlocked("existing_branch_without_pr")
    base = api.call("GET", "git/commits/" + base_sha)
    base_tree = base["tree"]["sha"]
    entries = []
    for path, encoded in files:
        blob = api.call("POST", "git/blobs", {"content": encoded, "encoding": "base64"})
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    tree = api.call("POST", "git/trees", {"base_tree": base_tree, "tree": entries})
    commit = api.call("POST", "git/commits", {"message": "Core8 review artifact " + idem[:16],
                                                "tree": tree["sha"], "parents": [base_sha]})
    api.call("POST", "git/refs", {"ref": "refs/heads/" + branch, "sha": commit["sha"]})
    description = (marker + "\nDraft review of an already human-approved Claude artifact.\n"
                   + "Scope SHA256: " + scope_sha + "\nArtifact SHA256: " + artifact_sha
                   + "\nBase commit: " + base_sha + "\nNo merge or deploy authorization.\n")
    pr = api.call("POST", "pulls", {"title": "[Review only] Core8 generated patch " + idem[:12],
                                          "head": branch, "base": "main", "draft": True, "body": description})
    return {"status": "CREATED_DRAFT", "url": pr["html_url"], "branch": branch}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--scope-sha256", required=True)
    parser.add_argument("--artifact-sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        with open(args.bundle, "rb") as stream:
            raw = stream.read(MAX_BUNDLE + 1)
        idem, files = inspect_bundle(raw, args.bundle_sha256, base_sha=args.base_sha,
                                     scope_sha=args.scope_sha256, artifact_sha=args.artifact_sha256)
        if not args.apply:
            print(json.dumps({"status": "VALIDATED_NO_WRITE", "idempotency_key": idem,
                              "file_count": len(files)}, sort_keys=True))
            return 0
        if os.getenv("CORE8_PROTECTED_PUBLISH") != "1" or not os.getenv("GITHUB_TOKEN"):
            raise PublishBlocked("protected_environment_and_token_required")
        result = publish(GitHubApi(args.repo, os.environ["GITHUB_TOKEN"]), repo=args.repo,
                         base_sha=args.base_sha, bundle_raw=raw, bundle_hash=args.bundle_sha256,
                         scope_sha=args.scope_sha256, artifact_sha=args.artifact_sha256)
        print(json.dumps(result, sort_keys=True))
    except (OSError, PublishBlocked, HttpFailed, KeyError, TypeError) as exc:
        print("BLOCKED:", type(exc).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
