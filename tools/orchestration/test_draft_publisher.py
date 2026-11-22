import base64
import hashlib
import json
import unittest
from draft_publisher import PublishBlocked, HttpFailed, inspect_bundle, publish

BASE = "a" * 40
SCOPE = "b" * 64
ARTIFACT = "c" * 64
REPO = "owner/repo"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bundle(path="docs/demo.md", content=b"hello"):
    idem = sha((BASE + ":" + ARTIFACT + ":" + SCOPE).encode())
    payload = {"schema": 1, "status": "REVIEW_ONLY", "base_sha": BASE,
               "approved_scope_sha256": SCOPE, "artifact_sha256": ARTIFACT,
               "idempotency_key": idem, "paths": [path],
               "files": [{"path": path, "sha256": sha(content),
                          "content_b64": base64.b64encode(content).decode()}]}
    raw = json.dumps(payload, sort_keys=True).encode()
    return raw, sha(raw)


class FakeApi:
    repo = REPO

    def __init__(self, existing=False, blocked_ref=False, main_sha=BASE):
        self.calls = []
        self.existing = existing
        self.blocked_ref = blocked_ref
        self.main_sha = main_sha

    def call(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if path.startswith("pulls?"):
            if not self.existing:
                return []
            idem = sha((BASE + ":" + ARTIFACT + ":" + SCOPE).encode())
            return [{"draft": True, "html_url": "https://github.com/owner/repo/pull/9",
                     "body": "<!-- core8-review:" + idem + " -->",
                     "head": {"ref": "core8-review/" + idem[:24], "repo": {"full_name": REPO}},
                     "base": {"ref": "main", "sha": BASE}}]
        if path == "git/ref/heads/main":
            return {"object": {"sha": self.main_sha}}
        if path.startswith("git/ref/heads/"):
            if self.blocked_ref:
                return {"ref": "existing"}
            raise HttpFailed(404)
        if path.startswith("git/commits/"):
            return {"tree": {"sha": "base-tree"}}
        if path == "git/blobs":
            return {"sha": "blob-sha"}
        if path == "git/trees":
            return {"sha": "tree-sha"}
        if path == "git/commits":
            return {"sha": "commit-sha"}
        if path == "git/refs":
            return {"ref": "created"}
        if path == "pulls":
            assert payload["draft"] is True and payload["base"] == "main"
            return {"html_url": "https://github.com/owner/repo/pull/10"}
        raise AssertionError(path)


def call_publish(api, data=None, hash_value=None):
    raw, expected = bundle() if data is None else (data, hash_value or sha(data))
    return publish(api, repo=REPO, base_sha=BASE, bundle_raw=raw, bundle_hash=expected,
                   scope_sha=SCOPE, artifact_sha=ARTIFACT)


class DraftPublisherTests(unittest.TestCase):
    def test_valid_bundle(self):
        raw, expected = bundle()
        idem, items = inspect_bundle(raw, expected, base_sha=BASE, scope_sha=SCOPE, artifact_sha=ARTIFACT)
        self.assertEqual(len(idem), 64)
        self.assertEqual(items[0][0], "docs/demo.md")

    def test_digest_tamper(self):
        raw, digest = bundle()
        with self.assertRaisesRegex(PublishBlocked, "bundle_digest_mismatch"):
            inspect_bundle(raw + b" ", digest, base_sha=BASE, scope_sha=SCOPE, artifact_sha=ARTIFACT)

    def test_scope_mismatch(self):
        raw, digest = bundle()
        with self.assertRaisesRegex(PublishBlocked, "scope_or_base_mismatch"):
            inspect_bundle(raw, digest, base_sha=BASE, scope_sha="d" * 64, artifact_sha=ARTIFACT)

    def test_forbidden_path(self):
        raw, digest = bundle(".github/workflows/auto.yml")
        with self.assertRaisesRegex(PublishBlocked, "forbidden_path"):
            inspect_bundle(raw, digest, base_sha=BASE, scope_sha=SCOPE, artifact_sha=ARTIFACT)

    def test_detect_secret(self):
        raw, digest = bundle(content=b"sk-ant-" + b"x" * 30)
        with self.assertRaisesRegex(PublishBlocked, "possible_secret"):
            inspect_bundle(raw, digest, base_sha=BASE, scope_sha=SCOPE, artifact_sha=ARTIFACT)

    def test_bad_content_sha(self):
        raw, _ = bundle()
        doc = json.loads(raw)
        doc["files"][0]["sha256"] = "0" * 64
        corrupt = json.dumps(doc).encode()
        with self.assertRaisesRegex(PublishBlocked, "file_data_mismatch_or_binary"):
            inspect_bundle(corrupt, sha(corrupt), base_sha=BASE, scope_sha=SCOPE, artifact_sha=ARTIFACT)

    def test_create_draft_only(self):
        api = FakeApi()
        result = call_publish(api)
        self.assertEqual(result["status"], "CREATED_DRAFT")
        self.assertEqual(api.calls[-1][:2], ("POST", "pulls"))
        self.assertTrue(api.calls[-1][2]["draft"])
        self.assertFalse(any("merge" in path for _, path, _ in api.calls))

    def test_existing_pr_is_idempotent(self):
        api = FakeApi(existing=True)
        result = call_publish(api)
        self.assertEqual(result["status"], "EXISTING_DRAFT")
        self.assertTrue(all(method == "GET" for method, _, _ in api.calls))

    def test_matching_but_non_draft_pr_fails_closed(self):
        api = FakeApi(existing=True)
        original = api.call

        def fail_non_draft(method, path, payload=None):
            result = original(method, path, payload)
            if path.startswith("pulls?"):
                result[0]["draft"] = False
            return result

        api.call = fail_non_draft
        with self.assertRaisesRegex(PublishBlocked, "conflicting_existing_pr"):
            call_publish(api)

    def test_forged_existing_draft_wrong_head_is_blocked(self):
        api = FakeApi(existing=True)
        original = api.call

        def forged(method, path, payload=None):
            response = original(method, path, payload)
            if path.startswith("pulls?"):
                response[0]["head"]["ref"] = "unrelated"
            return response

        api.call = forged
        with self.assertRaisesRegex(PublishBlocked, "conflicting_existing_pr"):
            call_publish(api)

    def test_existing_draft_wrong_base_sha_is_blocked(self):
        api = FakeApi(existing=True)
        original = api.call

        def stale(method, path, payload=None):
            response = original(method, path, payload)
            if path.startswith("pulls?"):
                response[0]["base"]["sha"] = "f" * 40
            return response

        api.call = stale
        with self.assertRaisesRegex(PublishBlocked, "conflicting_existing_pr"):
            call_publish(api)

    def test_orphan_branch_fails_closed(self):
        api = FakeApi(blocked_ref=True)
        with self.assertRaisesRegex(PublishBlocked, "existing_branch_without_pr"):
            call_publish(api)
        self.assertTrue(all(method == "GET" for method, _, _ in api.calls))

    def test_stale_main_blocks_before_any_write(self):
        api = FakeApi(main_sha="f" * 40)
        with self.assertRaisesRegex(PublishBlocked, "base_no_longer_main"):
            call_publish(api)
        self.assertTrue(all(method == "GET" for method, _, _ in api.calls))

    def test_wrong_repository(self):
        raw, digest = bundle()
        with self.assertRaisesRegex(PublishBlocked, "repository_mismatch"):
            publish(FakeApi(), repo="wrong/repo", base_sha=BASE, bundle_raw=raw,
                    bundle_hash=digest, scope_sha=SCOPE, artifact_sha=ARTIFACT)


if __name__ == "__main__":
    unittest.main()
