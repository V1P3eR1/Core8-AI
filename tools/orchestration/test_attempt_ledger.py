"""Offline lifecycle and corruption tests for the engineering attempt ledger."""
import copy
import unittest
from datetime import datetime, timedelta, timezone
from attempt_ledger import make_event, replay, history_for, InvalidLedger, GENESIS
from retry_policy import decide

TASK = "core8-draft-12"
SCOPE = "b" * 64
SHA = "a" * 40
NOW = datetime(2026, 11, 22, 13, 0, tzinfo=timezone.utc)
def at(offset):
    return (NOW + timedelta(minutes=offset)).isoformat()
def add(events, name, number, minutes):
    return events + [make_event(events, name, TASK, SCOPE, SHA, number, at(minutes))]

class AttemptLedgerTests(unittest.TestCase):
    def test_empty_and_successful_replay(self):
        self.assertEqual(replay([])["head"], GENESIS)
        events = add([], "attempt_started", 1, -100)
        events = add(events, "attempt_failed", 1, -90)
        self.assertEqual(replay(events)["event_count"], 2)
        hist = history_for(events, TASK, SCOPE, SHA)
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["result"], "failed")
        self.assertEqual(hist[0]["started_at"], at(-100))

    def test_duplicate_or_overlapping_attempt_refused(self):
        started = add([], "attempt_started", 1, -60)
        with self.assertRaises(InvalidLedger):
            add(started, "attempt_started", 1, -55)
        with self.assertRaises(InvalidLedger):
            add(started, "attempt_started", 2, -55)
        done = add(started, "attempt_failed", 1, -50)
        with self.assertRaises(InvalidLedger):
            add(done, "attempt_started", 1, -40)

    def test_failed_attempt_can_retry_once(self):
        events = add([], "attempt_started", 1, -80)
        events = add(events, "attempt_tested_failed", 1, -70)
        events = add(events, "attempt_started", 2, -35)
        events = add(events, "attempt_succeeded", 2, -15)
        history = history_for(events, TASK, SCOPE, SHA)
        self.assertEqual([x["result"] for x in history], ["tested_failed", "succeeded"])
        with self.assertRaises(InvalidLedger):
            add(events, "attempt_started", 3, 0)

    def test_cancelled_or_succeeded_attempt_does_not_retry(self):
        for ending in ("attempt_cancelled", "attempt_succeeded"):
            events = add([], "attempt_started", 1, -60)
            events = add(events, ending, 1, -50)
            with self.assertRaises(InvalidLedger):
                add(events, "attempt_started", 2, -20)

    def test_terminal_without_active_attempt_and_wrong_number_refused(self):
        with self.assertRaises(InvalidLedger):
            add([], "attempt_failed", 1, 0)
        events = add([], "attempt_started", 1, -30)
        with self.assertRaises(InvalidLedger):
            add(events, "attempt_failed", 2, -20)

    def test_tampered_event_content_and_reordered_lines_refused(self):
        events = add([], "attempt_started", 1, -60)
        events = add(events, "attempt_failed", 1, -50)
        edited = copy.deepcopy(events)
        edited[0]["task_id"] = "modified"
        with self.assertRaises(InvalidLedger):
            replay(edited)
        with self.assertRaises(InvalidLedger):
            replay(events[::-1])
        with self.assertRaises(InvalidLedger):
            replay(events[1:])

    def test_terminal_earlier_than_start_refused(self):
        events = add([], "attempt_started", 1, -10)
        with self.assertRaises(InvalidLedger):
            add(events, "attempt_failed", 1, -20)

    def test_unexpected_metadata_or_secret_field_refused(self):
        events = add([], "attempt_started", 1, -60)
        tampered = copy.deepcopy(events)
        tampered[0]["token"] = "do-not-accept"
        with self.assertRaises(InvalidLedger):
            replay(tampered)

    def test_attempts_integrate_with_advisory_retry_policy(self):
        events = add([], "attempt_started", 1, -90)
        events = add(events, "attempt_failed", 1, -80)
        history = history_for(events, TASK, SCOPE, SHA)
        task = {
            "task_id": TASK, "scope_digest": SCOPE,
            "approved": True, "approved_scope_digest": SCOPE,
            "approved_head_sha": SHA, "allow_paid_execution": True,
        }
        obs = {"head_sha": SHA, "state": "needs_human_triage"}
        suggestion = decide(task, obs, history, NOW)
        self.assertEqual(suggestion["action"], "propose_approved_patch_lane")
        self.assertEqual(suggestion["attempt"], 2)
        self.assertFalse(suggestion["execution_authorized"])

    def test_in_progress_event_never_allows_duplicate_claim(self):
        events = add([], "attempt_started", 1, -40)
        history = history_for(events, TASK, SCOPE, SHA)
        self.assertEqual(history[0]["result"], "in_progress")
        task = {
            "task_id": TASK, "scope_digest": SCOPE,
            "approved": True, "approved_scope_digest": SCOPE,
            "approved_head_sha": SHA, "allow_paid_execution": True,
        }
        obs = {"head_sha": SHA, "state": "needs_human_triage"}
        suggestion = decide(task, obs, history, NOW)
        self.assertEqual(suggestion["reason"], "previous_attempt_not_confirmed_failed")

if __name__ == "__main__":
    unittest.main()
