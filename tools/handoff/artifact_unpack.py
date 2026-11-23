"""Bounded in-memory extraction of a GitHub Actions Claude patch artifact.

The GitHub API digest authenticates the downloaded ZIP, not the extracted
patch. This module checks both boundaries without executing or writing files.
The caller must separately authenticate run metadata and human task approval.
"""
import hashlib
import io
import re
import stat
import zipfile

MAX_ARCHIVE = 5_000_000
MAX_PATCH = 300_000
EXPECTED_MEMBER = "core8-implementation.patch"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class UnsafeArtifact(ValueError):
    """Fixed non-sensitive reason code for a failed artifact check."""


def extract_verified_patch(archive_bytes, *, trusted_archive_sha256):
    if (not isinstance(trusted_archive_sha256, str)
            or not HEX64.fullmatch(trusted_archive_sha256)):
        raise UnsafeArtifact("invalid_trusted_archive_digest")
    if (not isinstance(archive_bytes, bytes) or not archive_bytes
            or len(archive_bytes) > MAX_ARCHIVE):
        raise UnsafeArtifact("invalid_archive_size")
    if hashlib.sha256(archive_bytes).hexdigest() != trusted_archive_sha256:
        raise UnsafeArtifact("archive_digest_mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r", allowZip64=False) as zf:
            entries = zf.infolist()
            if len(entries) != 1 or entries[0].filename != EXPECTED_MEMBER:
                raise UnsafeArtifact("unexpected_archive_members")
            entry = entries[0]
            if (entry.is_dir() or entry.flag_bits & 0x1
                    or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                raise UnsafeArtifact("unsafe_archive_member")
            mode = entry.external_attr >> 16
            if mode:
                file_type = stat.S_IFMT(mode)
                if file_type not in (0, stat.S_IFREG):
                    raise UnsafeArtifact("unsafe_archive_file_mode")
            if (entry.file_size <= 0 or entry.file_size > MAX_PATCH
                    or entry.compress_size <= 0
                    or entry.file_size > 200 * entry.compress_size):
                raise UnsafeArtifact("archive_bomb_or_oversize")
            patch = zf.read(entry)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, OSError, EOFError):
        raise UnsafeArtifact("archive_decode_failed") from None
    if len(patch) == 0 or len(patch) > MAX_PATCH or b"\x00" in patch:
        raise UnsafeArtifact("invalid_extracted_patch")
    return {
        "patch_bytes": patch,
        "patch_sha256": hashlib.sha256(patch).hexdigest(),
        "archive_sha256": trusted_archive_sha256,
    }
