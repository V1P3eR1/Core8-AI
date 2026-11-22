#!/usr/bin/env python3
"""Fail-closed structural gate for untrusted Core8 Claude patch artifacts.

Does not apply, execute or publish a patch. Follow with git apply --check
in an isolated checkout with no secrets or write-capable credentials.
"""
import argparse
import hashlib
import re
import sys
from pathlib import PurePosixPath

MAX_PATCH_BYTES = 256 * 1024
MAX_FILES = 30
ALLOWED_ROOTS = ("apps/", "docs/")
BLOCKED_PARTS = {".git", ".github", "node_modules", "__pycache__", ".env", "secrets", "credentials"}
BLOCKED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".sqlite", ".db")
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(rb"(?:sk-ant-|sk-proj-|ghp_|github_pat_|ntn_)[A-Za-z0-9_-]{12,}"),
)
HEADER = re.compile(r"^diff --git a/([^\s]+) b/([^\s]+)$")


class RejectedPatch(ValueError):
    pass


def validate_path(path: str) -> None:
    if not path or len(path) > 240 or "\\" in path or "\x00" in path or path.startswith(("/", "~")):
        raise RejectedPatch("invalid_path")
    p = PurePosixPath(path)
    if str(p) != path or any(part in (".", "..") for part in path.split("/")):
        raise RejectedPatch("path_traversal_or_normalization")
    if not path.startswith(ALLOWED_ROOTS) or len(p.parts) < 2:
        raise RejectedPatch("outside_allowed_roots")
    if any(part.lower() in BLOCKED_PARTS or part.lower().startswith(".env") for part in p.parts):
        raise RejectedPatch("sensitive_path")
    if path.lower().endswith(BLOCKED_SUFFIXES):
        raise RejectedPatch("sensitive_extension")


def validate_patch(payload: bytes, expected_sha256: str) -> dict:
    if not payload or len(payload) > MAX_PATCH_BYTES:
        raise RejectedPatch("empty_or_oversize")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise RejectedPatch("invalid_digest")
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected_sha256:
        raise RejectedPatch("digest_mismatch")
    if b"\x00" in payload or b"GIT binary patch" in payload or b"Binary files " in payload:
        raise RejectedPatch("binary_patch")
    if any(pattern.search(payload) for pattern in SECRET_PATTERNS):
        raise RejectedPatch("possible_secret")
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise RejectedPatch("not_utf8") from exc
    paths = []
    for line in lines:
        match = HEADER.fullmatch(line)
        if match:
            a, b = match.groups()
            if a != b:
                raise RejectedPatch("rename_not_allowed")
            validate_path(a)
            if a in paths:
                raise RejectedPatch("duplicate_file")
            paths.append(a)
            if len(paths) > MAX_FILES:
                raise RejectedPatch("too_many_files")
            continue
        if line.startswith(("rename from ", "rename to ", "copy from ", "copy to ", "Submodule ")):
            raise RejectedPatch("rename_copy_or_submodule")
        if line.startswith(("new file mode ", "old mode ", "new mode ", "deleted file mode ")):
            mode = line.split()[-1]
            if mode != "100644":
                raise RejectedPatch("nonregular_mode")
        if line.startswith("--- ") and not (line == "--- /dev/null" or any(line == f"--- a/{p}" for p in paths)):
            raise RejectedPatch("invalid_old_path")
        if line.startswith("+++ ") and not any(line == f"+++ b/{p}" for p in paths):
            raise RejectedPatch("invalid_new_path")
    if not paths or not any(line.startswith("@@ ") for line in lines):
        raise RejectedPatch("missing_diff_hunks")
    return {"sha256": actual, "files": paths, "bytes": len(payload)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("patch", help="read-only path to patch artifact")
    parser.add_argument("--sha256", required=True, help="expected digest from trusted run metadata")
    args = parser.parse_args()
    try:
        with open(args.patch, "rb") as stream:
            payload = stream.read(MAX_PATCH_BYTES + 1)
        result = validate_patch(payload, args.sha256)
    except (RejectedPatch, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    print(f"VALID: sha256={result['sha256']} files={len(result['files'])} bytes={result['bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
