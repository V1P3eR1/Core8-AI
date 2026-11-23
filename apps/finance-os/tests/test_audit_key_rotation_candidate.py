"""Unit tests for synthetic, locally pinned audit HMAC rotation."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_key_rotation_candidate import (
    AuditKeyringCandidate, PinnedAuditKey,
    RotatingAuditReceiverCandidate, RotatingAuditSinkCandidate,
)
from audit_receiver_sqlite_candidate import SQLiteAuditReceiverCandidate
from tenant_access import FinanceAccessDenied

OLD = PinnedAuditKey("key_old", b"ci-audit-old-signing-key-synthetic-32-bytes")
NEW = PinnedAuditKey("key_new", b"ci-audit-new-signing-key-synthetic-32-bytes")
THIRD = PinnedAuditKey("key_third", b"ci-audit-third-signing-key-synthetic-32-bytes")


class AuditRotationCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "audit-receiver.sqlite")
        self.raw = SQLiteAuditReceiverCandidate(self.path)
        self.raw.initialize_test_store()
        self.namespace = "ci_audit_a"
        self.sender_keys = AuditKeyringCandidate(active=OLD)
        self.receiver_keys = AuditKeyringCandidate(active=OLD)
        self.receiver = RotatingAuditReceiverCandidate(
            receiver=self.raw, namespace=self.namespace, keyring=self.receiver_keys
        )
        self.sender = RotatingAuditSinkCandidate(
            receiver=self.receiver, namespace=self.namespace,
            keyring=self.sender_keys,
        )
        self.event = "finance-approval-audit-201"
        self.payload = {"event_id": self.event, "action": "consumed",
                        "approval_id": "ci-approval-201"}

    def tearDown(self):
        self.temp.cleanup()

    def count(self):
        with sqlite3.connect(self.path) as db:
            return db.execute(
                "SELECT count(*) FROM received_audit_candidate"
            ).fetchone()[0]

    def test_rotation_overlap_retire_and_refuse_old_key_revival(self):
        old_kid, old_sig = self.sender_keys.sign(
            namespace=self.namespace, event_id=self.event, payload=self.payload
        )
        self.assertTrue(self.sender.accept(self.event, self.payload))
        self.assertEqual(self.sender_keys.rotate(
            expected_generation=1, new_active=NEW, retain=(OLD.kid,)
        ), 2)
        self.assertEqual(self.receiver_keys.rotate(
            expected_generation=1, new_active=NEW, retain=(OLD.kid,)
        ), 2)
        self.receiver_keys.verify(
            namespace=self.namespace, event_id=self.event,
            payload=self.payload, kid=old_kid, signature=old_sig,
        )
        self.assertTrue(self.sender.accept(self.event, self.payload))
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.receiver_keys.rotate(
            expected_generation=2, new_active=NEW
        ), 3)
        with self.assertRaises(FinanceAccessDenied):
            self.receiver_keys.verify(
                namespace=self.namespace, event_id=self.event,
                payload=self.payload, kid=old_kid, signature=old_sig,
            )
        with self.assertRaises(FinanceAccessDenied):
            self.receiver_keys.rotate(
                expected_generation=3, new_active=OLD
            )
        self.assertEqual(self.receiver_keys.generation, 3)

    def test_rotation_cannot_reuse_existing_kid_with_different_secret(self):
        with self.assertRaises(FinanceAccessDenied):
            self.receiver_keys.rotate(
                expected_generation=1,
                new_active=PinnedAuditKey("key_old", NEW.secret),
            )
        self.assertEqual(self.receiver_keys.generation, 1)

    def test_wrong_generation_and_bad_retention_are_noop(self):
        for args in (
            {"expected_generation": 2, "new_active": NEW},
            {"expected_generation": 1, "new_active": NEW,
             "retain": ("missing_key",)},
            {"expected_generation": 1, "new_active": NEW,
             "retain": (OLD.kid, OLD.kid)},
            {"expected_generation": True, "new_active": NEW},
            {"expected_generation": 1, "new_active": PinnedAuditKey(
                "invalid key", NEW.secret)},
        ):
            with self.subTest(args=args):
                with self.assertRaises(FinanceAccessDenied):
                    self.receiver_keys.rotate(**args)
                self.assertEqual(self.receiver_keys.generation, 1)

    def test_cross_namespace_and_signature_substitution_denied(self):
        kid, sig = self.sender_keys.sign(
            namespace=self.namespace, event_id=self.event, payload=self.payload
        )
        for args in (
            {"namespace": "ci_audit_b", "event_id": self.event,
             "payload": self.payload, "kid": kid, "signature": sig},
            {"namespace": self.namespace, "event_id": self.event,
             "payload": {**self.payload, "approval_id": "tampered"},
             "kid": kid, "signature": sig},
            {"namespace": self.namespace, "event_id": self.event,
             "payload": self.payload, "kid": "key_unknown", "signature": sig},
            {"namespace": self.namespace, "event_id": self.event,
             "payload": self.payload, "kid": kid, "signature": "0" * 64},
        ):
            with self.subTest(args=args):
                with self.assertRaises(FinanceAccessDenied):
                    self.receiver.accept_signed(**args)
        self.assertEqual(self.count(), 0)

    def test_reject_duplicate_or_tombstoned_pinned_keyset(self):
        for kwargs in (
            {"active": OLD, "verify_only": (OLD,)},
            {"active": OLD, "retired": (OLD.kid,)},
            {"active": PinnedAuditKey("key_short", b"short")},
            {"active": OLD, "generation": True},
            {"active": OLD, "verify_only": (NEW, THIRD, OLD)},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(FinanceAccessDenied):
                    AuditKeyringCandidate(**kwargs)


if __name__ == "__main__":
    unittest.main()
