import hashlib
import io
import stat
import unittest
import zipfile
from artifact_unpack import UnsafeArtifact, extract_verified_patch

PATCH = b"diff --git a/docs/a.md b/docs/a.md\n"
MEMBER = "core8-implementation.patch"


def build_archive(*, members=None, method=zipfile.ZIP_DEFLATED, mode=None):
    file_obj = io.BytesIO()
    with zipfile.ZipFile(file_obj, "w", compression=method) as archive:
        for name, body in (members or [(MEMBER, PATCH)]):
            info = zipfile.ZipInfo(name)
            info.compress_type = method
            if mode is not None:
                info.create_system = 3
                info.external_attr = mode << 16
            archive.writestr(info, body)
    return file_obj.getvalue()


def extract(data, expected=None):
    sha = hashlib.sha256(data).hexdigest() if expected is None else expected
    return extract_verified_patch(data, trusted_archive_sha256=sha)


class ArtifactUnpackTests(unittest.TestCase):
    def test_valid_zip(self):
        result = extract(build_archive())
        self.assertEqual(result["patch_bytes"], PATCH)
        self.assertEqual(result["patch_sha256"], hashlib.sha256(PATCH).hexdigest())
        self.assertNotEqual(result["archive_sha256"], result["patch_sha256"])

    def test_stored_zip(self):
        self.assertEqual(extract(build_archive(method=zipfile.ZIP_STORED))["patch_bytes"], PATCH)

    def test_bad_archive_digest(self):
        with self.assertRaisesRegex(UnsafeArtifact, "archive_digest_mismatch"):
            extract(build_archive(), expected="0" * 64)

    def test_missing_archive_digest(self):
        with self.assertRaises(UnsafeArtifact):
            extract(build_archive(), expected="wrong")

    def test_not_zip(self):
        with self.assertRaisesRegex(UnsafeArtifact, "archive_decode_failed"):
            extract(b"not zip")

    def test_unexpected_filename(self):
        with self.assertRaisesRegex(UnsafeArtifact, "unexpected_archive_members"):
            extract(build_archive(members=[("../escape.patch", PATCH)]))

    def test_double_member(self):
        with self.assertRaisesRegex(UnsafeArtifact, "unexpected_archive_members"):
            extract(build_archive(members=[(MEMBER, PATCH), ("extra", b"bad")]))

    def test_duplicate_name(self):
        with self.assertRaisesRegex(UnsafeArtifact, "unexpected_archive_members"):
            extract(build_archive(members=[(MEMBER, PATCH), (MEMBER, PATCH)]))

    def test_empty_patch(self):
        with self.assertRaisesRegex(UnsafeArtifact, "archive_bomb_or_oversize"):
            extract(build_archive(members=[(MEMBER, b"")]))

    def test_symlink_mode_rejected(self):
        with self.assertRaisesRegex(UnsafeArtifact, "unsafe_archive_file_mode"):
            extract(build_archive(mode=stat.S_IFLNK | 0o777))

    def test_regular_mode_accepted(self):
        self.assertEqual(extract(build_archive(mode=stat.S_IFREG | 0o644))["patch_bytes"], PATCH)

    def test_directory_name_rejected(self):
        with self.assertRaises(UnsafeArtifact):
            extract(build_archive(members=[(MEMBER + "/", PATCH)]))

    def test_oversize_patch(self):
        with self.assertRaisesRegex(UnsafeArtifact, "archive_bomb_or_oversize"):
            extract(build_archive(members=[(MEMBER, b"x" * 300001)]))

    def test_bzip2_rejected(self):
        with self.assertRaisesRegex(UnsafeArtifact, "unsafe_archive_member"):
            extract(build_archive(method=zipfile.ZIP_BZIP2))

    def test_binary_patch_rejected(self):
        with self.assertRaisesRegex(UnsafeArtifact, "invalid_extracted_patch"):
            extract(build_archive(members=[(MEMBER, b"data\x00binary")]))


if __name__ == "__main__":
    unittest.main()
