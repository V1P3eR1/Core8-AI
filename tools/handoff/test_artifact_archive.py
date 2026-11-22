import hashlib
import io
import stat
import unittest
import zipfile

from artifact_archive import ArchiveRejected, EXPECTED_MEMBER, verify_artifact_zip


def make_zip(content=b"diff --git a/docs/new.md b/docs/new.md\n", name=EXPECTED_MEMBER, mode=0o100644):
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as z:
        item = zipfile.ZipInfo(name)
        item.external_attr = mode << 16
        item.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(item, content)
    return bio.getvalue()


def verified(archive):
    return verify_artifact_zip(archive, "sha256:" + hashlib.sha256(archive).hexdigest())


class ArtifactZipTests(unittest.TestCase):
    def test_valid_zip_has_distinct_patch_digest(self):
        archive = make_zip()
        output = verified(archive)
        self.assertEqual(output["patch_sha256"], hashlib.sha256(output["patch_bytes"]).hexdigest())
        self.assertEqual(output["archive_sha256"], hashlib.sha256(archive).hexdigest())
        self.assertNotEqual(output["patch_sha256"], output["archive_sha256"])

    def test_wrong_archive_hash(self):
        with self.assertRaisesRegex(ArchiveRejected, "archive_digest_mismatch"):
            verify_artifact_zip(make_zip(), "sha256:" + "a" * 64)

    def test_inner_patch_digest_not_accepted_as_archive_digest(self):
        payload = b"patch"
        with self.assertRaisesRegex(ArchiveRejected, "archive_digest_mismatch"):
            verify_artifact_zip(make_zip(payload), "sha256:" + hashlib.sha256(payload).hexdigest())

    def test_wrong_member(self):
        with self.assertRaisesRegex(ArchiveRejected, "unexpected_archive_members"):
            verified(make_zip(name="../other.patch"))

    def test_extra_member(self):
        obj = io.BytesIO()
        with zipfile.ZipFile(obj, "w") as z:
            z.writestr(EXPECTED_MEMBER, "patch")
            z.writestr("other.txt", "payload")
        with self.assertRaisesRegex(ArchiveRejected, "unexpected_archive_members"):
            verified(obj.getvalue())

    def test_symlink_rejected(self):
        with self.assertRaisesRegex(ArchiveRejected, "unsafe_archive_file_type"):
            verified(make_zip(b"/tmp/secret", mode=stat.S_IFLNK | 0o777))

    def test_oversize_patch(self):
        with self.assertRaisesRegex(ArchiveRejected, "invalid_patch_size"):
            verified(make_zip(b"a" * (256 * 1024 + 1)))

    def test_bad_archive(self):
        blob = b"not-a-zip"
        with self.assertRaisesRegex(ArchiveRejected, "invalid_zip"):
            verified(blob)

    def test_empty_patch(self):
        with self.assertRaisesRegex(ArchiveRejected, "invalid_patch_size"):
            verified(make_zip(b""))

    def test_invalid_digest_format(self):
        with self.assertRaisesRegex(ArchiveRejected, "invalid_trusted_archive_digest"):
            verify_artifact_zip(make_zip(), "not-sha")


if __name__ == "__main__":
    unittest.main()
