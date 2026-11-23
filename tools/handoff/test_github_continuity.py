import copy
import unittest

from github_continuity import (
    CHAINS, NoRedirect, SnapshotBlocked, get_json, make_snapshot,
    render_markdown, summarize_pr,
)

REPO = "V1P3eR1/Core8-AI"
SHA = "a" * 40


def fake_pr(number, state="open"):
    return {"number": number, "state": state, "draft": True, "merged_at": None,
            "head": {"sha": SHA, "repo": {"full_name": REPO}},
            "base": {"ref": "main"}}


def run(name, *, event="pull_request", status="completed", conclusion="success"):
    return {"name": name, "head_sha": SHA,
            "head_repository": {"full_name": REPO},
            "event": event, "status": status, "conclusion": conclusion}


def fake_runs(number=74):
    names = ["secret-scan",
             "Orchestration staging offline unit tests" if number in (67, 74) else
             "release preflight (offline)" if number in (55, 70) else
             "Finance OS sandbox unit tests" if number == 64 else
             "backend-tests" if number == 81 else
             "social-content-draft-contract" if number == 84 else
             "lead-contract-offline" if number == 85 else
             "Handoff contract tests"]
    values = [run(x) for x in names]
    return {"total_count": len(values), "workflow_runs": values}


class ContinuityTests(unittest.TestCase):
    def test_all_known_chains_bounded_and_never_approval(self):
        calls = []
        def fetch(path):
            calls.append(path)
            if path.startswith("/pulls/"):
                return fake_pr(int(path.split("/")[-1]))
            number = next((n for n in sum((list(v) for v in CHAINS.values()), [])
                           if False), None)
            # A workflow snapshot must never need any task/approval API.
            return fake_runs()
        snapshot = make_snapshot(fetch, checked_at="2026-11-23T09:00:00+00:00")
        self.assertEqual(sum(len(v) for v in snapshot["chains"].values()),
                         sum(map(len, CHAINS.values())))
        self.assertFalse(snapshot["execution_authorized"])
        self.assertFalse(snapshot["github_write_performed"])
        self.assertEqual(snapshot["notion_state"], "NOT_VERIFIED")
        self.assertIn("[#85]", render_markdown(snapshot))
        self.assertTrue(all(p.startswith(("/pulls/", "/actions/runs?")) for p in calls))

    def test_known_suites_green(self):
        for n in (55, 64, 65, 67, 70, 74, 80, 81, 84, 85):
            with self.subTest(n=n):
                self.assertEqual(summarize_pr(fake_pr(n), fake_runs(n), n)["check_state"], "passed")

    def test_demo_without_dedicated_suite_is_not_green(self):
        for n in (82, 83):
            with self.subTest(n=n):
                self.assertEqual(summarize_pr(fake_pr(n), fake_runs(n), n)["check_state"],
                                 "suite_policy_missing")

    def test_missing_required_workflow_is_not_green(self):
        r = fake_runs(85)
        r["workflow_runs"] = [run("secret-scan")]
        r["total_count"] = 1
        self.assertEqual(summarize_pr(fake_pr(85), r, 85)["check_state"],
                         "missing_required_workflows")

    def test_push_run_does_not_qualify_as_pr_check(self):
        r = fake_runs(85)
        r["workflow_runs"][1]["event"] = "push"
        self.assertEqual(summarize_pr(fake_pr(85), r, 85)["check_state"],
                         "missing_required_workflows")

    def test_duplicate_workflow_names_rejected(self):
        r = fake_runs(85)
        r["workflow_runs"].append(copy.deepcopy(r["workflow_runs"][1]))
        r["total_count"] += 1
        with self.assertRaisesRegex(SnapshotBlocked, "duplicate_workflow_names"):
            summarize_pr(fake_pr(85), r, 85)

    def test_partial_workflow_page_rejected(self):
        r = fake_runs()
        r["total_count"] = 200
        with self.assertRaisesRegex(SnapshotBlocked, "incomplete_workflow_inventory"):
            summarize_pr(fake_pr(74), r, 74)

    def test_no_runs_is_not_green(self):
        r = {"total_count": 0, "workflow_runs": []}
        self.assertEqual(summarize_pr(fake_pr(74), r, 74)["check_state"], "no_runs")

    def test_failed_required_run_not_green(self):
        r = fake_runs(85)
        r["workflow_runs"][1]["conclusion"] = "failure"
        self.assertEqual(summarize_pr(fake_pr(85), r, 85)["check_state"], "needs_review")

    def test_pending_required_run_not_green(self):
        r = fake_runs(85)
        r["workflow_runs"][1].update({"status": "in_progress", "conclusion": None})
        self.assertEqual(summarize_pr(fake_pr(85), r, 85)["check_state"], "pending")

    def test_sha_mismatch_rejected(self):
        r = fake_runs(85)
        r["workflow_runs"][0]["head_sha"] = "f" * 40
        with self.assertRaisesRegex(SnapshotBlocked, "workflow_provenance_mismatch"):
            summarize_pr(fake_pr(85), r, 85)

    def test_foreign_run_repo_rejected(self):
        r = fake_runs(85)
        r["workflow_runs"][0]["head_repository"]["full_name"] = "attacker/repo"
        with self.assertRaisesRegex(SnapshotBlocked, "workflow_provenance_mismatch"):
            summarize_pr(fake_pr(85), r, 85)

    def test_foreign_pr_repo_rejected(self):
        p = fake_pr(85)
        p["head"]["repo"]["full_name"] = "attacker/repo"
        with self.assertRaisesRegex(SnapshotBlocked, "unexpected_head_repository"):
            summarize_pr(p, fake_runs(85), 85)

    def test_closed_and_merged_prs_historical_only(self):
        p = fake_pr(85, state="closed")
        self.assertEqual(summarize_pr(p, fake_runs(85), 85)["check_state"],
                         "historical_only")
        p["merged_at"] = "2026-11-23T09:00:00Z"
        self.assertEqual(summarize_pr(p, fake_runs(85), 85)["state"], "merged")
        self.assertEqual(summarize_pr(p, fake_runs(85), 85)["check_state"],
                         "historical_only")

    def test_invalid_pr_number_rejected(self):
        with self.assertRaisesRegex(SnapshotBlocked, "pr_identity_mismatch"):
            summarize_pr(fake_pr(74), fake_runs(74), 85)

    def test_untrusted_api_paths_blocked_before_network(self):
        for path in ("/issues/85", "/actions/runs", "/pulls/85/merge",
                     "/actions/runs?head_sha=" + SHA + "&per_page=999",
                     "https://evil.example", "/commits/" + SHA + "/check-runs"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(SnapshotBlocked, "invalid_endpoint"):
                    get_json(path)

    def test_exact_safe_workflow_api_path_validates_past_regex(self):
        # Must not reject valid URL as invalid_endpoint: it will attempt GET.
        # No live network requests in unit tests; patch the URL opener.
        from unittest.mock import patch
        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): return None
            def geturl(self):
                return "https://api.github.com/repos/" + REPO + "/actions/runs?head_sha=" + SHA + "&per_page=100"
            def read(self, n): return b'{"total_count":0,"workflow_runs":[]}'
        class Opener:
            def open(self, req, timeout): return Response()
        with patch("github_continuity.request.build_opener", return_value=Opener()):
            item = get_json("/actions/runs?head_sha=" + SHA + "&per_page=100")
        self.assertEqual(item["total_count"], 0)

    def test_refuse_redirect_with_token(self):
        self.assertIsNone(NoRedirect().redirect_request(
            None, None, 302, "redirect", {}, "https://evil.example"))

    def test_no_private_title_or_body_export(self):
        p = fake_pr(85)
        p["body"] = "PRIVATE_TASK_DATA"
        p["title"] = "CUSTOMER_SECRET"
        record = summarize_pr(p, fake_runs(85), 85)
        self.assertNotIn("PRIVATE_TASK_DATA", str(record))
        self.assertNotIn("CUSTOMER_SECRET", str(record))

    def test_unknown_successful_run_does_not_replace_required(self):
        r = {"total_count": 2, "workflow_runs": [run("arbitrary-job"), run("secret-scan")]}
        self.assertEqual(summarize_pr(fake_pr(85), r, 85)["check_state"],
                         "missing_required_workflows")


if __name__ == "__main__":
    unittest.main()
