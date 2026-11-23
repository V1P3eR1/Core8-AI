"""No-network checks for bounded repo-wide CI snapshot."""
import unittest
from repo_live_preview import capture, RepoPreviewError

SHA = "a" * 40

def pr(n, sha=SHA):
    return {"number": n, "state": "open", "head": {"sha": sha}, "draft": True}

def fixture(count=3, checks=None):
    calls = []
    def fetch(path, token):
        calls.append(path)
        if path == "/pulls?state=open&per_page=100":
            return [pr(i + 1, f"{i+1:040x}") for i in range(count)]
        if "/check-runs?" in path:
            return {"check_runs": checks if checks is not None else [
                {"name": "contract", "status": "completed",
                 "conclusion": "success", "started_at": "2026-11-23T08:00:00Z", "id": 1}
            ]}
        raise AssertionError("unexpected API call")
    return fetch, calls

class RepoLivePreviewTests(unittest.TestCase):
    def test_three_real_prs_without_writes(self):
        fetch, calls = fixture()
        result = capture(fetch=fetch)
        self.assertEqual(result["coverage"], "complete")
        self.assertEqual(result["scanned_prs"], 3)
        self.assertEqual(len(calls), 4)
        self.assertEqual(result["approval"], "not_granted")
        self.assertFalse(result["boundaries"]["may_spend"])
        self.assertTrue(all(item["state"] == "review_gate" for item in result["items"]))

    def test_explicit_cap_and_partial_coverage(self):
        fetch, calls = fixture(31)
        out = capture(fetch=fetch)
        self.assertEqual(out["coverage"], "partial")
        self.assertEqual(out["total_open_prs_lower_bound"], 31)
        self.assertEqual(out["scanned_prs"], 20)
        self.assertEqual(len(calls), 21)

    def test_empty_repo(self):
        fetch, calls = fixture(0)
        out = capture(fetch=fetch)
        self.assertEqual(out["scanned_prs"], 0)
        self.assertEqual(out["coverage"], "complete")

    def test_one_hundred_results_cannot_claim_complete(self):
        fetch, _ = fixture(100)
        out = capture(fetch=fetch)
        self.assertEqual(out["coverage"], "partial")

    def test_check_page_size_100_requires_review(self):
        checks = [{"name": "many", "id": i, "status": "completed",
                   "conclusion": "success"} for i in range(100)]
        fetch, _ = fixture(1, checks)
        with self.assertRaisesRegex(RepoPreviewError, "not_exhaustive"):
            capture(fetch=fetch)

    def test_untrusted_pr_body_never_exported(self):
        def fetch(path, token):
            if path.startswith("/pulls"):
                return [{**pr(7), "title": "SECRET_CUSTOMER",
                         "body": "SECRET_PRIVATE_NOTION_SCOPE"}]
            return {"check_runs": []}
        out = capture(fetch=fetch)
        self.assertNotIn("SECRET_CUSTOMER", str(out))
        self.assertNotIn("SECRET_PRIVATE_NOTION_SCOPE", str(out))

    def test_bad_duplicate_issue_and_missing_sha(self):
        def f(path, token):
            return [pr(1), pr(1)]
        with self.assertRaises(RepoPreviewError):
            capture(fetch=f)
        def f2(path, token):
            return [pr(1, sha="bogus")]
        with self.assertRaises(RepoPreviewError):
            capture(fetch=f2)

if __name__ == "__main__":
    unittest.main()
