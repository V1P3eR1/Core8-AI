#!/usr/bin/env python3
"""Review a Claude patch in a disposable offline Git snapshot.

This is NOT an approval gate, CI runner, GitHub publisher or security sandbox.
Trusted run metadata must be checked by the upstream human approval gate.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
from tools.handoff.patch_gate import RejectedPatch, validate_patch, validate_path

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SHA40 = re.compile(r"[0-9a-f]{40}\Z")


class StageRejected(ValueError):
    pass


def git(root, *args, data=None):
    # Never forward the caller's arbitrary environment into Git subprocesses.
    # In particular, this excludes API keys, credentials and injection variables.
    env = {"PATH": os.defpath, "HOME": "/nonexistent", "LC_ALL": "C",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_TERMINAL_PROMPT": "0"}
    cmd = ["git", "-c", "core.hooksPath=/dev/null", "-c", "protocol.allow=never",
           "-C", str(root), *args]
    try:
        p = subprocess.run(cmd, input=data, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=env, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StageRejected("git_unavailable") from exc
    if p.returncode:
        raise StageRejected("git_" + args[0].replace("-", "_") + "_failed")
    return p.stdout


def stage(repo, patch, artifact_hash, base_sha, approved_scope_hash, bundle_output=None):
    if not SHA256.fullmatch(artifact_hash) or not SHA256.fullmatch(approved_scope_hash) or not SHA40.fullmatch(base_sha):
        raise StageRejected("invalid_trusted_metadata")
    if hashlib.sha256(patch).hexdigest() != artifact_hash:
        raise StageRejected("artifact_hash_mismatch")
    # Supplement the upstream structural gate; this is NOT a DLP guarantee.
    if re.search(rb"(?:sk-ant-|sk-proj-|ghp_|github_pat_|ntn_)[A-Za-z0-9_-]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY-----", patch):
        raise StageRejected("possible_secret")
    try:
        summary = validate_patch(patch, artifact_hash)
    except RejectedPatch as exc:
        raise StageRejected("patch_" + str(exc)) from exc
    repo = Path(repo).resolve(strict=True)
    if not (repo / ".git").exists():
        raise StageRejected("not_a_git_checkout")
    if git(repo, "rev-parse", "HEAD").strip().decode() != base_sha:
        raise StageRejected("base_sha_mismatch")
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise StageRejected("dirty_source")
    with tempfile.TemporaryDirectory(prefix="core8-review-") as temp:
        target = Path(temp)
        archive = git(repo, "archive", "--format=tar", base_sha)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            for member in tar.getmembers():
                p = Path(member.name)
                if (p.is_absolute() or ".." in p.parts or member.issym()
                        or member.islnk() or member.isdev()):
                    raise StageRejected("unsafe_base_archive")
            tar.extractall(path=target, filter="data")
        git(target, "init", "-q")
        git(target, "-c", "user.name=Review", "-c", "user.email=review@invalid.local",
            "add", "--all")
        git(target, "-c", "user.name=Review", "-c", "user.email=review@invalid.local",
            "commit", "-qm", "temporary-base")
        git(target, "apply", "--check", "--whitespace=error", "-", data=patch)
        git(target, "apply", "--whitespace=error", "-", data=patch)
        roots = [r for r in ("apps", "docs") if (target / r).is_dir()]
        git(target, "add", "-N", "--", *roots)
        raw = git(target, "diff", "--name-status", "-z", "HEAD", "--", *roots).split(b"\0")
        if raw[-1] or (len(raw) - 1) % 2:
            raise StageRejected("invalid_git_status")
        paths = []
        for i in range(0, len(raw) - 1, 2):
            status, path = raw[i].decode("ascii"), raw[i + 1].decode("utf-8")
            if status not in ("A", "M", "D"):
                raise StageRejected("unexpected_git_change")
            validate_path(path)
            paths.append(path)
        if sorted(paths) != sorted(summary['files']):
            raise StageRejected("changed_paths_mismatch")
        git(target, "add", "--all", "--", *roots)
        for item in git(target, "ls-files", "-s", "-z", "--", *roots).split(b"\0"):
            if item and not item.startswith(b"100644 "):
                raise StageRejected("unsafe_file_mode")
        git(target, "diff", "--cached", "--check")
        delta = git(target, "diff", "--cached", "--binary", "HEAD")
        if not delta:
            raise StageRejected("empty_effective_change")
        key = hashlib.sha256((base_sha + ":" + artifact_hash + ":" + approved_scope_hash).encode()).hexdigest()
        bundle_digest = None
        if bundle_output is not None:
            output = Path(bundle_output).absolute()
            if output.parent.resolve() == repo or repo in output.parent.resolve().parents:
                raise StageRejected("bundle_must_be_outside_source")
            files = []
            for path in sorted(paths):
                candidate = target / path
                if not candidate.is_file() or candidate.is_symlink():
                    raise StageRejected("bundle_requires_regular_files_no_deletions")
                raw = candidate.read_bytes()
                if len(raw) > 100_000 or b"\x00" in raw:
                    raise StageRejected("bundle_file_too_large_or_binary")
                files.append({"path": path, "sha256": hashlib.sha256(raw).hexdigest(),
                              "content_b64": base64.b64encode(raw).decode("ascii")})
            bundle = {"schema": 1, "status": "REVIEW_ONLY", "base_sha": base_sha,
                      "approved_scope_sha256": approved_scope_hash,
                      "artifact_sha256": artifact_hash, "idempotency_key": key,
                      "paths": sorted(paths), "files": files}
            payload = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
            if len(payload) > 2_000_000:
                raise StageRejected("bundle_too_large")
            with output.open("xb") as stream:
                stream.write(payload)
            bundle_digest = hashlib.sha256(payload).hexdigest()
    result = {"schema": 1, "status": "REVIEW_ONLY", "base_sha": base_sha,
              "approved_scope_sha256": approved_scope_hash, "artifact_sha256": artifact_hash,
              "result_sha256": hashlib.sha256(delta).hexdigest(),
              "idempotency_key": key, "paths": sorted(paths)}
    if bundle_digest is not None:
        result["bundle_sha256"] = bundle_digest
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "patch", "artifact_sha256", "base_sha", "approved_scope_sha256"):
        parser.add_argument("--" + name.replace("_", "-"), required=True)
    parser.add_argument("--bundle-output", help="create reviewed evidence JSON outside source repo")
    args = parser.parse_args()
    try:
        with open(args.patch, "rb") as f:
            patch = f.read(300_001)
        result = stage(args.repo, patch, args.artifact_sha256, args.base_sha, args.approved_scope_sha256, bundle_output=args.bundle_output)
    except (StageRejected, OSError, tarfile.TarError) as exc:
        print("BLOCKED:", str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
