"""Synthetic HMAC transport tests; never contacts a remote service."""
import concurrent.futures
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_receiver_sqlite_candidate import SQLiteAuditReceiverCandidate
from signed_audit_transport_candidate import (
    SignedAuditReceiverCandidate, SignedAuditSinkCandidate,
    sign_audit_event, verify_audit_event,
)
from tenant_access import FinanceAccessDenied

KEY = b"ci-only-audit-signing-secret-32-byte-minimum"
OTHER = b"ci-only-wrong-receiver-signing-secret-32-byte-minimum"


class SignedTransportCandidateTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = str(Path(self.folder.name) / "audit-receiver.sqlite")
        self.raw = SQLiteAuditReceiverCandidate(self.path)
        self.raw.initialize_test_store()
        self.receiver = SignedAuditReceiverCandidate(
            receiver=self.raw, namespace="ci_tenant_a",
            verification_key=KEY,
        )
        self.sink = SignedAuditSinkCandidate(
            receiver=self.receiver, namespace="ci_tenant_a", signing_key=KEY,
        )
        self.event = "finance-approval-audit-101"
        self.payload = {
            "event_id": self.event,
            "action": "consumed",
            "approval_id": "approved-ci-123",
            "recorded_at": "2026-11-23T00:00:00Z",
        }

    def tearDown(self):
        self.folder.cleanup()

    def rows(self):
        with sqlite3.connect(self.path) as db:
            return db.execute("SELECT count(*) FROM received_audit_candidate").fetchone()[0]

    def signature(self, **kw):
        args = dict(secret=KEY, namespace="ci_tenant_a",
                    event_id=self.event, payload=self.payload)
        args.update(kw)
        return sign_audit_event(**args)

    def test_valid_signed_delivery_and_identical_replay_are_idempotent(self):
        self.assertTrue(self.sink.accept(self.event, self.payload))
        self.assertTrue(self.sink.accept(self.event, dict(self.payload)))
        self.assertEqual(self.rows(), 1)

    def test_wrong_key_and_signature_tampering_deny_without_write(self):
        wrong_sink = SignedAuditSinkCandidate(
            receiver=self.receiver, namespace="ci_tenant_a",
            signing_key=OTHER,
        )
        with self.assertRaises(FinanceAccessDenied):
            wrong_sink.accept(self.event, self.payload)
        invalid = self.signature()
        for bad in ("", invalid[:-1] + ("1" if invalid[-1] != "1" else "0"), None):
            with self.subTest(bad=bad):
                with self.assertRaises(FinanceAccessDenied):
                    self.receiver.accept_signed(
                        namespace="ci_tenant_a", event_id=self.event,
                        payload=self.payload, signature=bad,
                    )
        self.assertEqual(self.rows(), 0)

    def test_namespace_and_content_substitution_denied(self):
        tag = self.signature()
        attempts = [
            ("ci_tenant_b", self.event, self.payload, tag),
            ("ci_tenant_a", self.event,
             {**self.payload, "approval_id": "changed"}, tag),
            ("ci_tenant_a", "finance-approval-audit-102",
             {**self.payload, "event_id": "finance-approval-audit-102"}, tag),
        ]
        for namespace, event_id, payload, signature in attempts:
            with self.subTest(namespace=namespace, event=event_id):
                with self.assertRaises(FinanceAccessDenied):
                    self.receiver.accept_signed(
                        namespace=namespace, event_id=event_id,
                        payload=payload, signature=signature,
                    )
        self.assertEqual(self.rows(), 0)

    def test_invalid_key_size_and_bad_envelope_fail_closed(self):
        with self.assertRaises(FinanceAccessDenied):
            SignedAuditSinkCandidate(
                receiver=self.receiver, namespace="ci_tenant_a",
                signing_key=b"short",
            )
        with self.assertRaises(FinanceAccessDenied):
            sign_audit_event(
                secret=KEY, namespace="../wrong",
                event_id=self.event, payload=self.payload,
            )
        with self.assertRaises(FinanceAccessDenied):
            verify_audit_event(
                secret=KEY, namespace="ci_tenant_a",
                event_id=self.event,
                payload={**self.payload, "nan": float("nan")},
                signature="a" * 64,
            )
        self.assertEqual(self.rows(), 0)

    def test_concurrent_signed_duplicates_stored_once(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.sink.accept(
                self.event, dict(self.payload)), range(8)))
        self.assertEqual(results, [True] * 8)
        self.assertEqual(self.rows(), 1)


if __name__ == "__main__":
    unittest.main()
