"""No-network contract cases for the advisory retry policy."""
import unittest
from datetime import datetime, timedelta, timezone
from retry_policy import decide, MAX_ATTEMPTS

NOW = datetime(2026, 11, 22, 11, 0, tzinfo=timezone.utc)
SHA = "a" * 40
DIGEST = "b" * 64
T = {
    "task_id": "core8-draft-12",
    "scope_digest": DIGEST,
    "approved": True,
    "approved_scope_digest": DIGEST,
    "approved_head_sha": SHA,
    "allow_paid_execution": True,
}
O = {"head_sha": SHA, "state": "needs_human_triage"}
def attempt(at, result="failed", **overrides):
    return {
        "task_id": T["task_id"], "scope_digest": DIGEST, "head_sha": SHA,
        "started_at": at.isoformat(), "result": result, **overrides
    }

class RetryPolicyTests(unittest.TestCase):
    def test_single_proposal_is_not_approval(self):
        d = decide(T, O, [], NOW)
        self.assertEqual(d["action"], "propose_approved_patch_lane")
        self.assertEqual(d["attempt"], 1)
        self.assertFalse(d["execution_authorized"])
        self.assertFalse(d["may_spend"])
        self.assertTrue(d["owner_gate_still_required"])

    def test_no_exact_scope_approval(self):
        d = decide({**T, "approved_scope_digest": "c" * 64}, O, [], NOW)
        self.assertEqual(d["reason"], "missing_exact_owner_approval")

    def test_changed_sha_blocks_replay(self):
        self.assertEqual(decide(T, {**O, "head_sha": "c" * 40}, [], NOW)["reason"],
                         "stale_head_requires_approval")

    def test_pending_and_missing_evidence_never_retry(self):
        self.assertEqual(decide(T, {**O, "state": "checks_pending"}, [], NOW)["action"], "wait")
        self.assertEqual(decide(T, {**O, "state": "missing_check_evidence"}, [], NOW)["action"], "blocked")

    def test_clean_checks_require_human_review_not_new_patch(self):
        self.assertEqual(decide(T, {**O, "state": "review_gate"}, [], NOW)["action"], "human_review")

    def test_paid_execution_is_never_implicitly_authorized(self):
        d = decide({**T, "allow_paid_execution": False}, O, [], NOW)
        self.assertEqual(d["reason"], "paid_execution_not_approved")

    def test_first_failure_cooldown(self):
        d = decide(T, O, [attempt(NOW - timedelta(minutes=10))], NOW)
        self.assertEqual(d["reason"], "retry_cooldown")
        d2 = decide(T, O, [attempt(NOW - timedelta(minutes=31))], NOW)
        self.assertEqual(d2["action"], "propose_approved_patch_lane")
        self.assertEqual(d2["attempt"], 2)

    def test_two_failed_attempts_exhaust_retry_budget(self):
        history = [
            attempt(NOW - timedelta(minutes=90)),
            attempt(NOW - timedelta(minutes=45))
        ]
        self.assertEqual(len(history), MAX_ATTEMPTS)
        self.assertEqual(decide(T, O, history, NOW)["reason"], "retry_budget_exhausted")

    def test_unrelated_task_history_blocks(self):
        bad = attempt(NOW - timedelta(minutes=50), task_id="different-task")
        self.assertEqual(decide(T, O, [bad], NOW)["reason"], "history_scope_conflict")

    def test_head_change_between_attempts_blocks(self):
        bad = attempt(NOW - timedelta(minutes=50), head_sha="f" * 40)
        self.assertEqual(decide(T, O, [bad], NOW)["reason"], "head_changed_between_attempts")

    def test_nonfailed_previous_attempt_blocks(self):
        self.assertEqual(decide(T, O, [attempt(NOW - timedelta(minutes=50), "succeeded")], NOW)["reason"],
                         "previous_attempt_not_confirmed_failed")

    def test_future_timestamp_and_naive_clock_refused(self):
        self.assertEqual(decide(T, O, [attempt(NOW + timedelta(minutes=2))], NOW)["reason"], "invalid_attempt_history")
        self.assertEqual(decide(T, O, [], datetime(2026, 11, 22))["reason"], "clock_invalid")

    def test_malformed_inputs_fail_closed(self):
        cases = [(None, O, []), (T, None, []), (T, O, None), (T, O, [None]), (T, {**O, "state": []}, []), (T, O, [attempt(NOW, started_at=123)])]
        for task, observation, history in cases:
            with self.subTest(task=task, observation=observation, history=history):
                d = decide(task, observation, history, NOW)
                self.assertEqual(d["action"], "blocked")
                self.assertFalse(d["execution_authorized"])
                self.assertFalse(d["may_spend"])

    def test_invalid_identifiers_fail_closed(self):
        self.assertEqual(decide({**T, "scope_digest": "oops"}, O, [], NOW)["reason"], "invalid_task_identity")
        self.assertEqual(decide(T, {**O, "head_sha": "notSHA"}, [], NOW)["reason"], "invalid_current_ci_snapshot")

if __name__ == "__main__":
    unittest.main()
