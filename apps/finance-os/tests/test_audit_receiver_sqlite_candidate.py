"""Standalone receiver and lost-ack simulations; no remote audit provider."""
import concurrent.futures
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_receiver_sqlite_candidate import SQLiteAuditReceiverCandidate
from tenant_access import FinanceAccessDenied


class ReceiverCandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "independent-receiver.sqlite")
        self.receiver = SQLiteAuditReceiverCandidate(self.path)
        self.receiver.initialize_test_store()
        self.event_id = "finance-approval-audit-101"
        self.payload = {
            "event_id": self.event_id, "approval_id": "approved_ci_12345",
            "action": "consumed", "recorded_at": "2026-11-23T00:00:00Z",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def count(self):
        with sqlite3.connect(self.path) as db:
            return db.execute("SELECT count(*) FROM received_audit_candidate").fetchone()[0]

    def test_restart_replay_deduplicates_identical_event(self):
        self.assertTrue(self.receiver.accept(self.event_id, self.payload))
        reopened = SQLiteAuditReceiverCandidate(self.path)
        self.assertTrue(reopened.accept(self.event_id, dict(self.payload)))
        self.assertEqual(self.count(), 1)

    def test_collision_mismatched_payload_rejected(self):
        self.assertTrue(self.receiver.accept(self.event_id, self.payload))
        forged = {**self.payload, "approval_id": "different"}
        with self.assertRaises(FinanceAccessDenied):
            self.receiver.accept(self.event_id, forged)
        self.assertEqual(self.count(), 1)

    def test_concurrent_duplicate_accept_is_atomic(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            values = list(pool.map(lambda _: self.receiver.accept(self.event_id, self.payload),
                                   range(8)))
        self.assertEqual(values, [True] * 8)
        self.assertEqual(self.count(), 1)

    def test_reject_untrusted_schema_and_missing_file(self):
        for event_id, payload in (
            ("../evil", self.payload),
            (self.event_id, {"event_id": self.event_id, "action": "deleted",
                             "approval_id": "approved_ci_12345"}),
            (self.event_id, {"event_id": "finance-approval-audit-102",
                             "action": "consumed", "approval_id": "approved_ci_12345"}),
            (self.event_id, {"event_id": self.event_id,
                             "action": "consumed", "approval_id": "approved_ci_12345",
                             "bad": float("nan")}),
        ):
            with self.subTest(event_id=event_id, payload=payload):
                with self.assertRaises(FinanceAccessDenied):
                    self.receiver.accept(event_id, payload)
        self.assertEqual(self.count(), 0)

    def test_receiver_does_not_accept_when_write_fails(self):
        # Not creating the schema simulates an unavailable local receiver.
        other = SQLiteAuditReceiverCandidate(str(Path(self.tmp.name) / "not-initialized.sqlite"))
        with self.assertRaises(FinanceAccessDenied):
            other.accept(self.event_id, self.payload)
        self.assertEqual(self.count(), 0)


if __name__ == "__main__":
    unittest.main()
