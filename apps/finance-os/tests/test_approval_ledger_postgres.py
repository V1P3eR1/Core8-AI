"""Disposable PostgreSQL approval ledger concurrency and audit tests."""
import concurrent.futures
import os
import sys
import threading
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import psycopg
    READY = os.getenv("APP_ENV") == "test" and bool(os.getenv("DATABASE_URL"))
except ImportError:
    READY = False
from key_approval_candidate import StoredKeyApproval
from approval_ledger_postgres_candidate import (
    PostgresApprovalCandidate, provision_test_approval,
)
from tenant_access import FinanceAccessDenied


@unittest.skipUnless(READY, "CI disposable postgres required")
class ApprovalLedgerPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not READY:
            return
        cls.dsn = os.environ["DATABASE_URL"]
        source = (Path(__file__).resolve().parents[1] / "sql" /
                  "key_approval_candidate.sql").read_text()
        with psycopg.connect(cls.dsn) as db:
            for statement in source.split(";"):
                clean = "\n".join(line for line in statement.splitlines()
                                  if not line.lstrip().startswith("--")).strip()
                if clean:
                    db.execute(clean)

    @classmethod
    def tearDownClass(cls):
        if READY:
            with psycopg.connect(cls.dsn) as db:
                db.execute("DROP TABLE IF EXISTS finance_key_approval_audit_candidate")
                db.execute("DROP TABLE IF EXISTS finance_key_approval_candidate")

    def setUp(self):
        self.namespace = "ci_keys_" + uuid4().hex[:10]
        self.approval = StoredKeyApproval(
            approval_id="approval_" + uuid4().hex,
            requester_subject="manager_ci",
            approver_subject="approver_ci",
            proposal_sha256="a" * 64,
            expires_at=1900000300,
        )
        with psycopg.connect(self.dsn, autocommit=True) as db:
            provision_test_approval(db, namespace=self.namespace,
                                   approval=self.approval)

    def tearDown(self):
        with psycopg.connect(self.dsn) as db:
            db.execute("DELETE FROM finance_key_approval_audit_candidate WHERE approval_id=%s",
                       (self.approval.approval_id,))
            db.execute("DELETE FROM finance_key_approval_candidate WHERE approval_id=%s",
                       (self.approval.approval_id,))

    def consume(self, *, approval=None, namespace=None, now=1800000000):
        approval = approval or self.approval
        with psycopg.connect(self.dsn, autocommit=True) as db:
            return PostgresApprovalCandidate(
                db, namespace=namespace or self.namespace, now=now
            ).consume(approval.approval_id, approval)

    def audit_count(self):
        with psycopg.connect(self.dsn) as db:
            return db.execute(
                "SELECT count(*) FROM finance_key_approval_audit_candidate WHERE approval_id=%s",
                (self.approval.approval_id,),
            ).fetchone()[0]

    def test_approval_is_single_use_after_new_connection(self):
        self.assertTrue(self.consume())
        self.assertFalse(self.consume())
        self.assertEqual(self.audit_count(), 1)

    def test_concurrent_consumers_only_one_success_and_audit_record(self):
        barrier = threading.Barrier(2)
        def attempt(_):
            barrier.wait(timeout=10)
            return self.consume()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertCountEqual(results, [True, False])
        self.assertEqual(self.audit_count(), 1)

    def test_expired_wrong_namespace_and_changed_approval_denied(self):
        from dataclasses import replace
        self.assertFalse(self.consume(now=self.approval.expires_at))
        self.assertFalse(self.consume(namespace="other_namespace"))
        self.assertFalse(self.consume(approval=replace(
            self.approval, proposal_sha256="b" * 64)))
        self.assertEqual(self.audit_count(), 0)
        self.assertTrue(self.consume())
        self.assertEqual(self.audit_count(), 1)

    def test_audit_write_failure_rolls_back_consumption(self):
        with psycopg.connect(self.dsn, autocommit=True) as db:
            with self.assertRaises(psycopg.Error):
                with db.transaction():
                    db.execute(
                        "DROP TABLE finance_key_approval_audit_candidate"
                    )
                    # Intentionally fails because the audit table was dropped.
                    PostgresApprovalCandidate(
                        db, namespace=self.namespace, now=1800000000
                    ).consume(self.approval.approval_id, self.approval)
            # The DROP is rolled back with the consumption.
        self.assertEqual(self.audit_count(), 0)
        self.assertTrue(self.consume())
        self.assertEqual(self.audit_count(), 1)

    def test_provisioning_cannot_overwrite_existing_approval(self):
        with psycopg.connect(self.dsn, autocommit=True) as db:
            with self.assertRaises(FinanceAccessDenied):
                provision_test_approval(
                    db, namespace=self.namespace, approval=self.approval
                )
        self.assertEqual(self.audit_count(), 0)


if __name__ == "__main__":
    unittest.main()
