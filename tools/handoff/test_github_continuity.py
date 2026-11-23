import copy
import io
import unittest
from contextlib import redirect_stdout

from github_continuity import (
    BASE, CHAINS, NoRedirect, SnapshotBlocked, get_json, make_snapshot,
    render_markdown, summarize_pr,
)

REPO = "V1P3eR1/Core8-AI"
SHA = "a" * 40


def fake_pr(n):
    return {"number": n, "state": "open", "draft": True, "merged_at": None,
            "head": {"sha": SHA, "repo": {"full_name": REPO}},
            "base": {"ref": "main"}}


def fake_checks():
    return {"total_count": 4, "check_runs": [
        {"name": "Handoff contract tests", "status": "completed", "conclusion": "success"},
        {"name": "Orchestration staging offline unit tests", "status": "completed", "conclusion": "success"},
        {"name": "release preflight (offline)", "status": "completed", "conclusion": "success"},
        {"name": "secret-scan", "status": "completed", "conclusion": "success"},
    ]}


class ContinuityTests(unittest.TestCase):
    def test_snapshot_has_every_known_pr_and_is_never_authorization(self):
        def fetch(path):
            if path.startswith("/pulls/"):
                return fake_pr(int(path.split("/")[-1]))
            return fake_checks()
        snapshot = make_snapshot(fetch, checked_at="2026-11-22T15:00:00+00:00")
        self.assertEqual(sum(len(v) for v in snapshot["chains"].values()),
                         sum(len(c) for c in CHAINS.values()))
        self.assertEqual(snapshot["notion_state"], "NOT_VERIFIED")
        self.assertFalse(snapshot["execution_authorized"])
        self.assertFalse(snapshot["github_write_performed"])
        rendered = render_markdown(snapshot)
        self.assertIn("NOT VERIFIED", rendered)
        self.assertIn("NOT AUTHORIZED", rendered)
        self.assertIn("[#79]", rendered)

    def test_no_checks_never_green(self):
        item = summarize_pr(fake_pr(74), {"total_count": 0, "check_runs": []}, 74)
        self.assertEqual(item["check_state"], "no_checks")

    def test_pending_checks_never_green(self):
        checks = fake_checks()
        checks["check_runs"][1]["status"] = "in_progress"
        checks["check_runs"][1]["conclusion"] = None
        self.assertEqual(summarize_pr(fake_pr(74), checks, 74)["check_state"], "pending")

    def test_failed_check_never_green(self):
        checks = fake_checks()
        checks["check_runs"][1]["conclusion"] = "failure"
        self.assertEqual(summarize_pr(fake_pr(74), checks, 74)["check_state"], "needs_review")

    def test_unrelated_success_cannot_replace_required_ci(self):
        checks = {"total_count": 1, "check_runs": [
            {"name": "unit-tests", "status": "completed", "conclusion": "success"}]}
        self.assertEqual(
            summarize_pr(fake_pr(74), checks, 74)["check_state"],
            "missing_required_checks")

    def test_release_requires_release_preflight(self):
        checks = fake_checks()
        checks["check_runs"] = [c for c in checks["check_runs"]
                                if c["name"] != "release preflight (offline)"]
        checks["total_count"] = len(checks["check_runs"])
        self.assertEqual(
            summarize_pr(fake_pr(55), checks, 55)["check_state"],
            "missing_required_checks")

    def test_duplicate_check_names_fail_closed(self):
        checks = fake_checks()
        checks["check_runs"].append(copy.deepcopy(checks["check_runs"][0]))
        checks["total_count"] = 5
        with self.assertRaisesRegex(SnapshotBlocked, "duplicate_check_names"):
            summarize_pr(fake_pr(74), checks, 74)

    def test_partial_check_page_blocked(self):
        checks = fake_checks()
        checks["total_count"] = 99
        with self.assertRaisesRegex(SnapshotBlocked, "incomplete_check_inventory"):
            summarize_pr(fake_pr(74), checks, 74)

    def test_merged_pr_green_checks_are_historical_only(self):
        pr = fake_pr(74)
        pr["state"] = "closed"
        pr["merged_at"] = "2026-11-23T07:00:00Z"
        summary = summarize_pr(pr, fake_checks(), 74)
        self.assertEqual(summary["state"], "merged")
        self.assertEqual(summary["check_state"], "historical_only")

    def test_mismatched_check_run_sha_fails_closed(self):
        checks = fake_checks()
        checks["check_runs"][0]["head_sha"] = "f" * 40
        with self.assertRaisesRegex(SnapshotBlocked, "check_head_sha_mismatch"):
            summarize_pr(fake_pr(74), checks, 74)

    def test_matching_check_run_sha_is_allowed(self):
        checks = fake_checks()
        checks["check_runs"][0]["head_sha"] = SHA
        self.assertEqual(summarize_pr(fake_pr(74), checks, 74)["check_state"], "passed")

    def test_wrong_repo_rejected(self):
        pr = fake_pr(74)
        pr["head"]["repo"]["full_name"] = "attacker/repo"
        with self.assertRaisesRegex(SnapshotBlocked, "unexpected_head_repository"):
            summarize_pr(pr, fake_checks(), 74)

    def test_wrong_pr_number_rejected(self):
        with self.assertRaisesRegex(SnapshotBlocked, "pr_identity_mismatch"):
            summarize_pr(fake_pr(73), fake_checks(), 74)

    def test_closed_unmerged_not_reported_as_merged(self):
        pr = fake_pr(74)
        pr["state"] = "closed"
        summary = summarize_pr(pr, fake_checks(), 74)
        self.assertEqual(summary["state"], "closed")
        self.assertEqual(summary["check_state"], "historical_only")

    def test_inconsistent_merge_rejected(self):
        pr = fake_pr(74)
        pr["merged_at"] = "2026-11-22T12:00:00Z"
        with self.assertRaisesRegex(SnapshotBlocked, "inconsistent_merge_state"):
            summarize_pr(pr, fake_checks(), 74)

    def test_invalid_api_endpoint_rejected_before_network(self):
        for endpoint in ("/issues/74", "https://evil.test/", "/pulls/74/merge",
                         "/commits/" + SHA + "/check-runs?per_page=999"):
            with self.subTest(endpoint=endpoint):
                with self.assertRaisesRegex(SnapshotBlocked, "invalid_endpoint"):
                    get_json(endpoint)

    def test_bearer_redirect_not_followed(self):
        self.assertIsNone(
            NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://evil.test"))

    def test_pr_private_body_not_exported(self):
        pr = fake_pr(74)
        pr["body"] = "PRIVATE_TASK_PAYLOAD"
        pr["title"] = "SECRET_CUSTOMER_NAME"
        snap = summarize_pr(pr, fake_checks(), 74)
        self.assertNotIn("PRIVATE_TASK_PAYLOAD", str(snap))
        self.assertNotIn("SECRET_CUSTOMER_NAME", str(snap))

    def test_authentication_endpoint_never_used_for_approval(self):
        calls = []
        def fetch(p):
            calls.append(p)
            if p.startswith("/pulls/"):
                return fake_pr(int(p.split("/")[-1]))
            return fake_checks()
        make_snapshot(fetch, checked_at="2026-11-22T15:00:00+00:00")
        self.assertTrue(all(p.startswith(("/pulls/", "/commits/")) for p in calls))
        self.assertFalse(any("approval" in p or "notion" in p for p in calls))


if __name__ == "__main__":
    unittest.main()
