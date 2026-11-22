"""Verify GitHub artifact ZIP digest before trusting its inner patch.

GitHub artifact metadata digest hashes the downloaded ZIP, not the uncompressed
patch bytes. Caller must authenticate GitHub metadata and its approval gate.
"""
import hashlib
import io
import re
import stat
import zipfile

MAX_ARCHIVE_BYTES = 2 * 1024 * 1024
MAX_PATCH_BYTES = 256 * 1024
EXPECTED_MEMBER = "core8-implementation.patch"


class ArchiveRejected(ValueError):
    pass


def verify_artifact_zip(archive: bytes, trusted_github_digest: str):
    """Return verified uncompressed patch and two separately scoped hashes."""
    if not isinstance(archive, bytes) or not archive or len(archive) > MAX_ARCHIVE_BYTES:
        raise ArchiveRejected("invalid_archive_size")
    if not isinstance(trusted_github_digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", trusted_github_digest):
        raise ArchiveRejected("invalid_trusted_archive_digest")
    archive_digest = hashlib.sha256(archive).hexdigest()
    if trusted_github_digest != "sha256:" + archive_digest:
        raise ArchiveRejected("archive_digest_mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(archive), "r") as z:
            names = z.infolist()
            if len(names) != 1 or names[0].filename != EXPECTED_MEMBER:
                raise ArchiveRejected("unexpected_archive_members")
            info = names[0]
            mode = info.external_attr >> 16
            if info.is_dir() or stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                raise ArchiveRejected("unsafe_archive_file_type")
            if info.file_size == 0 or info.file_size > MAX_PATCH_BYTES:
                raise ArchiveRejected("invalid_patch_size")
            if info.flag_bits & 0x1:
                raise ArchiveRejected("encrypted_archive")
            if info.compress_size and info.file_size > 1000 * info.compress_size:
                raise ArchiveRejected("suspicious_compression_ratio")
            with z.open(info) as stream:
                patch = stream.read(MAX_PATCH_BYTES + 1)
            if len(patch) != info.file_size or b"\0" in patch:
                raise ArchiveRejected("invalid_extracted_patch")
    except (zipfile.BadZipFile, EOFError, RuntimeError, OSError, ValueError) as exc:
        if isinstance(exc, ArchiveRejected):
            raise
        raise ArchiveRejected("invalid_zip") from exc
    return {
        "patch_bytes": patch,
        "archive_sha256": archive_digest,
        "patch_sha256": hashlib.sha256(patch).hexdigest(),
        "member_name": EXPECTED_MEMBER,
    }
