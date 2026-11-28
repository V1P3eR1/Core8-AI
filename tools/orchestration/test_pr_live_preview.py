"""No-network validation of GitHub current-head live preview."""
import unittest
from pr_live_preview import snapshot, PreviewError

SHA = "a" * 40

def pr(sha=SHA, state="open", repo="V1P3eR1/Core8-AI"):
    return {"number": 61, "state": state,
            "head": {"sha": sha, "repo": {"full_name": repo}}, "draft": True}

def check():
    return {"name": "integration", "id": 100, "status": "completed",
            "conclusion": "success", "started_at": "2026-11-23T10:00:00Z"}

def fetching(pr_data=None, check_data=None):
    calls = []
    def fetch(path, token):
        calls.append(path)
        if path == "/pulls/61":
            return pr_data if pr_data is not None else pr()
        if path == f"/commits/{SHA}/check-runs?per_page=100":
            return check_data if check_data is not None else {"check_runs": [check()]}
        raise AssertionError(f"unexpected API path: {path}")
    return fetch, calls

class LivePreviewTests(unittest.TestCase):
    def test_valid_current_head_observation(self):
        fetch, calls = fetching()
        result = snapshot(61, SHA, fetch=fetch)
        self.assertEqual(calls, ["/pulls/61", f"/commits/{SHA}/check-runs?per_page=100"])
        self.assertEqual(result["source"], "github_current_head_pr")
        self.assertTrue(result["snapshot_only"])
        self.assertEqual(result["scanned_prs"], 1)
        self.assertEqual(result["items"][0]["state"], "review_gate")
        self.assertEqual(result["approval"], "not_granted")
        self.assertFalse(result["boundaries"]["may_merge"])

    def test_pr_head_change_fails_before_check_lookup(self):
        fetch, calls = fetching(pr_data=pr(sha="b" * 40))
        with self.assertRaisesRegex(PreviewError, "stale_pr_head"):
            snapshot(61, SHA, fetch=fetch)
        self.assertEqual(calls, ["/pulls/61"])

    def test_forked_or_closed_pr_refused(self):
        for item in [pr(repo="other/fork"), pr(state="closed")]:
            fetch, _ = fetching(pr_data=item)
            with self.assertRaises(PreviewError):
                snapshot(61, SHA, fetch=fetch)

    def test_invalid_sha_and_numbers_refused_before_network(self):
        fetch, calls = fetching()
        for n, sha in [(0, SHA), (True, SHA), (61, "X" * 40), (61, "")]:
            with self.assertRaises(PreviewError):
                snapshot(n, sha, fetch=fetch)
        self.assertFalse(calls)

    def test_no_check_evidence_is_not_a_pass(self):
        fetch, _ = fetching(check_data={"check_runs": []})
        row = snapshot(61, SHA, fetch=fetch)["items"][0]
        self.assertEqual(row["state"], "missing_check_evidence")

    def test_running_check_is_not_misrepresented_as_success(self):
        fetch, _ = fetching(check_data={
            "check_runs": [{"name": "contract", "id": 100, "status": "in_progress",
                            "conclusion": None, "started_at": "2026-11-23T10:00:00Z"}]})
        row = snapshot(61, SHA, fetch=fetch)["items"][0]
        self.assertEqual(row["state"], "checks_pending")

    def test_truncated_check_evidence_rejected(self):
        fetch, _ = fetching(check_data={"check_runs": [check()] * 101})
        with self.assertRaisesRegex(PreviewError, "truncated_check_evidence"):
            snapshot(61, SHA, fetch=fetch)

    def test_no_issue_text_or_private_scope_propagates(self):
        payload = pr()
        payload["body"] = "SENSITIVE_NOTION_SCOPE_SHOULD_NOT_EXPORT"
        payload["title"] = "Customer identifying title"
        fetch, _ = fetching(pr_data=payload)
        result = snapshot(61, SHA, fetch=fetch)
        self.assertNotIn("SENSITIVE_NOTION_SCOPE_SHOULD_NOT_EXPORT", str(result))
        self.assertNotIn("Customer identifying title", str(result))

if __name__ == "__main__":
    unittest.main()
