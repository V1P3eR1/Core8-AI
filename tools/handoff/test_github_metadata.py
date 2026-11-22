import copy
import unittest

from github_metadata import MetadataRejected, REPO, API, validate_github_metadata

HASH = "a" * 64
RUN_SHA = "b" * 40


def fixtures():
    return {
        "actions/runs/123": {
            "id": 123, "name": "Core8 approved Claude patch",
            "event": "issue_comment", "status": "completed",
            "conclusion": "success", "head_sha": RUN_SHA,
            "created_at": "2026-11-22T10:05:00Z",
            "actor": {"id": 42}, "repository": {"full_name": REPO},
        },
        "actions/artifacts/456": {
            "id": 456, "name": "core8-implementation-patch", "expired": False,
            "size_in_bytes": 1800, "digest": "sha256:" + "c" * 64,
            "workflow_run": {"id": 123},
            "created_at": "2026-11-22T10:06:00Z",
            "expires_at": "2026-11-29T10:06:00Z",
        },
        "issues/comments/789": {
            "id": 789, "user": {"id": 42},
            "issue_url": API + "issues/20",
            "created_at": "2026-11-22T10:00:00Z",
            "body": "/core8-implement " + HASH,
        },
    }


class GithubMetadataTests(unittest.TestCase):
    def setUp(self):
        self.data = fixtures()
        self.paths = []

    def get(self, path, token):
        self.assertEqual(token, "read-token")
        self.paths.append(path)
        return copy.deepcopy(self.data[path])

    def check(self):
        return validate_github_metadata(
            run_id=123, artifact_id=456, comment_id=789,
            token="read-token", get=self.get)

    def test_valid_metadata(self):
        result = self.check()
        self.assertEqual(result["task_digest"], HASH)
        self.assertEqual(result["archive_digest"], "sha256:" + "c" * 64)
        self.assertEqual(result["issue_number"], 20)
        self.assertEqual(len(self.paths), 3)

    def test_wrong_repository(self):
        self.data["actions/runs/123"]["repository"]["full_name"] = "other/repo"
        with self.assertRaisesRegex(MetadataRejected, "wrong_repository"):
            self.check()

    def test_failed_run(self):
        self.data["actions/runs/123"]["conclusion"] = "failure"
        with self.assertRaisesRegex(MetadataRejected, "wrong_workflow_or_result"):
            self.check()

    def test_wrong_workflow(self):
        self.data["actions/runs/123"]["name"] = "anything"
        with self.assertRaisesRegex(MetadataRejected, "wrong_workflow_or_result"):
            self.check()

    def test_artifact_wrong_run(self):
        self.data["actions/artifacts/456"]["workflow_run"]["id"] = 100
        with self.assertRaisesRegex(MetadataRejected, "artifact_run_mismatch"):
            self.check()

    def test_missing_digest(self):
        self.data["actions/artifacts/456"].pop("digest")
        with self.assertRaisesRegex(MetadataRejected, "missing_github_zip_digest"):
            self.check()

    def test_expired_artifact(self):
        self.data["actions/artifacts/456"]["expired"] = True
        with self.assertRaisesRegex(MetadataRejected, "expired_artifact"):
            self.check()

    def test_forged_comment_author(self):
        self.data["issues/comments/789"]["user"]["id"] = 9000
        with self.assertRaisesRegex(MetadataRejected, "unrelated_approval_comment"):
            self.check()

    def test_forged_comment_scope(self):
        self.data["issues/comments/789"]["body"] = "/core8-implement " + HASH + " please"
        with self.assertRaisesRegex(MetadataRejected, "not_a_hash_approval"):
            self.check()

    def test_wrong_comment_issue_url(self):
        self.data["issues/comments/789"]["issue_url"] = "https://evil.test/issues/20"
        with self.assertRaisesRegex(MetadataRejected, "wrong_issue_url"):
            self.check()

    def test_approval_after_run(self):
        self.data["issues/comments/789"]["created_at"] = "2026-11-22T11:00:00Z"
        with self.assertRaisesRegex(MetadataRejected, "invalid_provenance_time"):
            self.check()

    def test_approval_outside_window(self):
        self.data["issues/comments/789"]["created_at"] = "2026-11-20T09:00:00Z"
        with self.assertRaisesRegex(MetadataRejected, "approval_outside_run_window"):
            self.check()

    def test_invalid_identifier(self):
        with self.assertRaisesRegex(MetadataRejected, "invalid_identifiers"):
            validate_github_metadata(run_id=True, artifact_id=456, comment_id=789,
                                     token="read-token", get=self.get)


if __name__ == "__main__":
    unittest.main()
