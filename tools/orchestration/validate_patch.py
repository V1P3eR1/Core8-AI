"""Admission-only validator for *untrusted* agent patches.

This does not apply, execute, commit, push or approve a patch. It is one
defense-in-depth gate for a future isolated patch-to-draft-PR worker.
"""
import re
import sys
from pathlib import PurePosixPath

MAX_BYTES = 160_000
MAX_FILES = 20
MAX_LINES = 2500
ALLOWED = ("apps/", "docs/")
BLOCKED = ("/deploy/", "/.github/", "/node_modules/", "/.git/", "/secrets/",
           "/keys/", "/.env", "/private/", "/credentials/", "/dist/")
SENSITIVE = re.compile(r"(?:^|/)(?:Dockerfile|Caddyfile|.*\.(?:key|pem|p12|pfx|env|sh|exe|dll|so|bin))$", re.I)
SECRET = re.compile(
    r"(?:sk-(?:ant-|proj-)?[A-Za-z0-9_-]{16,}|"
    r"(?:ghp_|github_pat_|ntn_)[A-Za-z0-9_]{16,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)", re.I
)

class Rejected(ValueError):
    pass


def allowed_path(name):
    if not name or name.startswith("/") or "\\" in name or "\0" in name:
        return False
    path = PurePosixPath(name)
    if ".." in path.parts or "." in path.parts or "//" in name:
        return False
    if not name.startswith(ALLOWED) or any(x in "/" + name.lower() for x in BLOCKED):
        return False
    if SENSITIVE.search(name):
        return False
    if any(segment.startswith(".") for segment in path.parts):
        return False
    return True


def validate_patch(content):
    if not isinstance(content, bytes) or len(content) > MAX_BYTES or not content:
        raise Rejected("invalid_size")
    if b"\0" in content:
        raise Rejected("binary_patch")
    try:
        text = content.decode("utf-8", errors="strict")
    except UnicodeError:
        raise Rejected("invalid_encoding") from None
    if SECRET.search(text):
        raise Rejected("possible_secret")
    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        raise Rejected("too_many_lines")
    if not text.endswith("\n"):
        raise Rejected("missing_final_newline")
    paths = []
    current = None
    seen_hunk = False
    for line in lines:
        if line.startswith("diff --git "):
            m = re.fullmatch(r"diff --git a/(\S+) b/(\S+)", line)
            if not m or m[1] != m[2] or not allowed_path(m[1]):
                raise Rejected("invalid_path_or_rename")
            current = m[1]
            if current in paths:
                raise Rejected("duplicate_file")
            paths.append(current)
            if len(paths) > MAX_FILES:
                raise Rejected("too_many_files")
        elif line.startswith(("new file mode ", "new mode ", "old mode ", "deleted file mode ")) and line != "new file mode 100644":
            raise Rejected("unsupported_file_mode")
        elif line.startswith("index ") and re.search(r"\s(?:100755|120000|160000)$", line):
            raise Rejected("unsupported_file_mode")
        elif line.startswith(("rename ", "copy ", "GIT binary patch", "Binary files ",
                              "old mode", "new mode", "deleted file mode",
                              "new file mode 100755", "new file mode 120000",
                              "index 160000", "Submodule ")):
            raise Rejected("unsupported_patch_metadata")
        elif line.startswith(("--- ", "+++ ")):
            if current is None:
                raise Rejected("missing_file_header")
            expected = "a/" + current if line.startswith("--- ") else "b/" + current
            if line[4:] not in (expected, "/dev/null"):
                raise Rejected("header_path_mismatch")
        elif line.startswith("@@ "):
            if current is None or not re.match(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", line):
                raise Rejected("invalid_hunk")
            seen_hunk = True
        elif line.startswith("+") and not line.startswith("+++"):
            # The secret check above also applies to new lines.
            if current is None:
                raise Rejected("unscoped_addition")
    if not paths or not seen_hunk:
        raise Rejected("no_reviewable_changes")
    return {"admission": "structural_only", "files": len(paths),
            "paths": paths, "bytes": len(content),
            "is_approved_for_execution": False}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_patch.py <candidate.patch>")
    try:
        with open(sys.argv[1], "rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        result = validate_patch(data)
        print("patch_structure_ok files=" + str(result["files"]) +
              " execution_authorized=false")
    except (OSError, Rejected):
        print("patch_admission_rejected", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
