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
    """Strict structural gate. Isolated git apply --check remains mandatory."""
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_PATCH_BYTES:
        raise RejectedPatch("empty_or_oversize")
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise RejectedPatch("invalid_digest")
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected_sha256:
        raise RejectedPatch("digest_mismatch")
    if b"\x00" in payload or any(p.search(payload) for p in SECRET_PATTERNS):
        raise RejectedPatch("binary_or_possible_secret")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise RejectedPatch("not_utf8") from None
    if "\r" in text:
        raise RejectedPatch("invalid_line_ending")
    lines = text.splitlines()
    index_line = re.compile(r"^index [0-9a-f]{7,64}\.\.[0-9a-f]{7,64}(?: 100644)?$")
    hunk_line = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")
    paths = []
    i = 0
    while i < len(lines):
        m = HEADER.fullmatch(lines[i])
        if not m or m.group(1) != m.group(2):
            raise RejectedPatch("invalid_diff_header")
        path = m.group(1)
        validate_path(path)
        if path in paths or len(paths) >= 20:
            raise RejectedPatch("duplicate_or_too_many_files")
        paths.append(path)
        section_start = i
        i += 1
        creating = False
        if i < len(lines) and lines[i].startswith(("new file mode ", "deleted file mode ")):
            if lines[i] != "new file mode 100644":
                raise RejectedPatch("unsafe_mode_or_deletion")
            creating = True
            i += 1
        if i >= len(lines) or not index_line.fullmatch(lines[i]):
            raise RejectedPatch("invalid_index")
        i += 1
        old_header = "--- /dev/null" if creating else f"--- a/{path}"
        if i + 1 >= len(lines) or lines[i] != old_header or lines[i + 1] != f"+++ b/{path}":
            raise RejectedPatch("mismatched_file_headers")
        i += 2
        hunks = 0
        while i < len(lines) and not lines[i].startswith("diff --git "):
            match = hunk_line.fullmatch(lines[i])
            if not match:
                raise RejectedPatch("invalid_hunk_header")
            before = int(match.group(2) or 1)
            after = int(match.group(4) or 1)
            if before + after > 100000:
                raise RejectedPatch("hunk_too_large")
            i += 1
            hunks += 1
            while before or after:
                if i >= len(lines):
                    raise RejectedPatch("truncated_hunk")
                line = lines[i]
                if not line or line[0] not in (" ", "+", "-"):
                    raise RejectedPatch("invalid_hunk_line")
                if line[0] == " ":
                    before -= 1
                    after -= 1
                elif line[0] == "-":
                    before -= 1
                else:
                    after -= 1
                if before < 0 or after < 0:
                    raise RejectedPatch("hunk_count_mismatch")
                i += 1
                if i < len(lines) and lines[i] == r"\ No newline at end of file":
                    i += 1
        if not hunks or sum(len(s.encode("utf-8")) + 1 for s in lines[section_start:i]) > 100000:
            raise RejectedPatch("missing_hunks_or_file_too_large")
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
    print(f"STRUCTURE_VALID: sha256={result['sha256']} files={len(result['files'])} bytes={result['bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
