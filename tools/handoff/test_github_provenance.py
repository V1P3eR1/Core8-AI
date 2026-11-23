import hashlib
import io
import json
import unittest
from github_provenance import (REPO, REPO_ID, WORKFLOW_PATH, ARTIFACT_NAME,
                               EvidenceBlocked, GitHubReadOnly,
                               validate_run_artifact)


class FakeResponse:
    def __init__(self, content):
        self._file = io.BytesIO(content)
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def read(self, size=-1): return self._file.read(size)


class FakeOpener:
    def __init__(self, run, artifact):
        self.run, self.artifact = run, artifact
        self.requests = []
    def open(self, request, timeout):
        self.requests.append(request)
        if request.full_url.endswith("/actions/runs/123"):
            obj = self.run
        elif request.full_url.endswith("/actions/artifacts/456"):
            obj = self.artifact
        else:
            raise AssertionError("unexpected endpoint")
        return FakeResponse(json.dumps(obj).encode())


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.run = dict(id=123, repository=dict(full_name=REPO, id=REPO_ID),
                        event="issue_comment", head_branch="main", head_sha=self.sha,
                        path=WORKFLOW_PATH, status="completed", conclusion="success",
                        run_attempt=1, actor={"id": 999}, triggering_actor={"id": 999})
        self.artifact = dict(id=456, name=ARTIFACT_NAME, expired=False,
                             digest="sha256:" + "b" * 64,
                             created_at="2026-11-22T10:00:00Z",
                             expires_at="2026-11-29T10:00:00Z",
                             workflow_run=dict(id=123, head_sha=self.sha,
                                               head_branch="main", repository_id=REPO_ID))

    def check(self, run=None, artifact=None):
        return validate_run_artifact(run or self.run, artifact or self.artifact,
                                     run_id=123, artifact_id=456, head_sha=self.sha,
                                     expected_actor_id=999)

    def test_valid_metadata(self):
        self.assertEqual(self.check()["archive_sha256"], "b" * 64)
        self.assertNotIn("artifact_sha256", self.check())

    def test_archive_digest_is_not_patch_digest(self):
        record = self.check()
        self.assertIn("archive_sha256", record)
        self.assertNotIn("artifact_sha256", record)
        self.assertNotIn("patch_sha256", record)

    def test_get_only_fixed_endpoints(self):
        opener = FakeOpener(self.run, self.artifact)
        result = GitHubReadOnly("placeholder-read-token", opener=opener).fetch_verified(
            run_id=123, artifact_id=456, head_sha=self.sha,
            expected_actor_id=999)
        self.assertEqual(result["artifact_id"], 456)
        self.assertEqual([x.get_method() for x in opener.requests], ["GET", "GET"])
        self.assertTrue(all(x.full_url.startswith("https://api.github.com/repos/" + REPO + "/")
                            for x in opener.requests))

    def test_disallow_arbitrary_api_resources_before_network(self):
        opener = FakeOpener(self.run, self.artifact)
        reader = GitHubReadOnly("placeholder-read-token", opener=opener)
        for path in ("../users/1", "actions/runs/123/..", "issues/0",
                     "issues/comments/-1", "actions/runs/123?ref=main",
                     "https://evil.invalid/test", "issues/1%2Fcomments"):
            with self.subTest(path=path), self.assertRaisesRegex(
                    EvidenceBlocked, "github_resource_not_allowed"):
                reader._get(path)
        self.assertEqual(opener.requests, [])

    def test_issue_evidence_paths_still_allowed(self):
        self.assertEqual(
            [bool(__import__("github_provenance").ALLOWED_RESOURCE.fullmatch(path))
             for path in ("issues/62", "issues/comments/456")], [True, True])

    def test_duplicate_json_keys_rejected(self):
        class DuplicateOpener:
            def open(self, request, timeout):
                return FakeResponse(b'{"id": 123, "id": 456}')
        reader = GitHubReadOnly("placeholder-read-token", opener=DuplicateOpener())
        with self.assertRaisesRegex(EvidenceBlocked, "github_duplicate_json_key"):
            reader._get("actions/runs/123")

    def test_redirected_final_url_rejected(self):
        class RedirectedResponse(FakeResponse):
            def geturl(self):
                return "https://evil.invalid/redirected"
        class RedirectOpener:
            def open(self, request, timeout):
                return RedirectedResponse(b'{}')
        reader = GitHubReadOnly("placeholder-read-token", opener=RedirectOpener())
        with self.assertRaisesRegex(EvidenceBlocked, "github_redirect_refused"):
            reader._get("actions/runs/123")

    def test_forged_run_actor_rejected(self):
        self.run["actor"]["id"] = 111
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_forged_triggering_actor_rejected(self):
        self.run["triggering_actor"]["id"] = 111
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_missing_actor_rejected(self):
        del self.run["actor"]
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_wrong_trusted_approver_rejected(self):
        with self.assertRaises(EvidenceBlocked):
            validate_run_artifact(self.run, self.artifact, run_id=123,
                                  artifact_id=456, head_sha=self.sha, expected_actor_id=1000)

    def test_bool_actor_rejected(self):
        self.run["actor"]["id"] = True
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_other_repo_rejected(self):
        self.run["repository"]["full_name"] = "attacker/repo"
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_wrong_repository_id_rejected(self):
        self.run["repository"]["id"] = 111
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_wrong_workflow_rejected(self):
        self.run["path"] = ".github/workflows/untrusted.yml"
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_other_trigger_rejected(self):
        self.run["event"] = "push"
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_failed_run_rejected(self):
        self.run["conclusion"] = "failure"
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_rerun_rejected(self):
        self.run["run_attempt"] = 2
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_wrong_head_rejected(self):
        self.run["head_sha"] = "f" * 40
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_unrelated_artifact_rejected(self):
        self.artifact["workflow_run"]["id"] = 999
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_expired_artifact_rejected(self):
        self.artifact["expired"] = True
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_missing_provider_digest_rejected(self):
        self.artifact["digest"] = None
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_bad_provider_digest_rejected(self):
        self.artifact["digest"] = "sha256:" + "z" * 64
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_wrong_artifact_name_rejected(self):
        self.artifact["name"] = "other"
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_invalid_run_id_rejected(self):
        with self.assertRaises(EvidenceBlocked):
            GitHubReadOnly("fake").fetch_verified(run_id=True, artifact_id=456, head_sha=self.sha,
                                                         expected_actor_id=999)

    def test_missing_token_rejected(self):
        with self.assertRaises(EvidenceBlocked): GitHubReadOnly("")

    def test_wrong_head_branch_rejected(self):
        self.artifact["workflow_run"]["head_branch"] = "feature/untrusted"
        with self.assertRaises(EvidenceBlocked): self.check()

    def test_wrong_artifact_id_rejected(self):
        self.artifact["id"] = 457
        with self.assertRaises(EvidenceBlocked): self.check()


if __name__ == "__main__":
    unittest.main()
