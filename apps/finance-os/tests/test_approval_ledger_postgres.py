"""Disposable PostgreSQL approval ledger concurrency and audit tests."""
import concurrent.futures
import os
import time
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
            guard_sql = (Path(__file__).resolve().parents[1] / "sql" /
                         "key_approval_audit_guard_candidate.sql").read_text()
            # PL/pgSQL function has internal semicolons; separate by blank
            # paragraphs rather than splitting the function on semicolons.
            for command in guard_sql.split("\n\n"):
                if command.strip() and not command.lstrip().startswith("--"):
                    db.execute(command)
                elif command.strip():
                    # Initial comment paragraph includes the CREATE FUNCTION.
                    db.execute(command)

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
            expires_at=int(time.time()) + 300,
        )
        with psycopg.connect(self.dsn, autocommit=True) as db:
            provision_test_approval(db, namespace=self.namespace,
                                   approval=self.approval)

    # CI uses unique approval IDs per test. Retain records until the entire
    # disposable test table is dropped at tearDownClass, because audit entries
    # must never be deleted during ordinary operations.

    def consume(self, *, approval=None, namespace=None):
        approval = approval or self.approval
        with psycopg.connect(self.dsn, autocommit=True) as db:
            return PostgresApprovalCandidate(
                db, namespace=namespace or self.namespace
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
        with psycopg.connect(self.dsn, autocommit=True) as db:
            db.execute(
                "UPDATE finance_key_approval_candidate SET expires_at=%s WHERE approval_id=%s",
                (int(time.time()) - 1, self.approval.approval_id),
            )
        self.assertFalse(self.consume())
        with psycopg.connect(self.dsn, autocommit=True) as db:
            db.execute(
                "UPDATE finance_key_approval_candidate SET expires_at=%s WHERE approval_id=%s",
                (self.approval.expires_at, self.approval.approval_id),
            )
        self.assertFalse(self.consume(namespace="other_namespace"))
        self.assertFalse(self.consume(approval=replace(
            self.approval, proposal_sha256="b" * 64)))
        self.assertEqual(self.audit_count(), 0)
        self.assertTrue(self.consume())
        self.assertEqual(self.audit_count(), 1)

    def test_nested_transaction_cannot_replay_consumed_approval(self):
        # Consuming inside a caller transaction would return True before
        # commit, allowing a later rollback to make the approval reusable.
        with psycopg.connect(self.dsn, autocommit=True) as db:
            with db.transaction():
                ledger = PostgresApprovalCandidate(
                    db, namespace=self.namespace
                )
                with self.assertRaises(FinanceAccessDenied):
                    ledger.consume(self.approval.approval_id, self.approval)
        self.assertEqual(self.audit_count(), 0)
        self.assertTrue(self.consume())
        self.assertEqual(self.audit_count(), 1)

    def test_non_autocommit_connection_denied(self):
        with psycopg.connect(self.dsn) as db:
            ledger = PostgresApprovalCandidate(db, namespace=self.namespace)
            with self.assertRaises(FinanceAccessDenied):
                ledger.consume(self.approval.approval_id, self.approval)
        self.assertEqual(self.audit_count(), 0)
        self.assertTrue(self.consume())

    def test_server_clock_rejects_expired_and_far_future_approval(self):
        from dataclasses import replace
        with psycopg.connect(self.dsn, autocommit=True) as db:
            for delta in (-60, 7200):
                with self.subTest(delta=delta):
                    expiry = int(time.time()) + delta
                    db.execute(
                        "UPDATE finance_key_approval_candidate SET expires_at=%s WHERE approval_id=%s",
                        (expiry, self.approval.approval_id),
                    )
                    candidate = replace(self.approval, expires_at=expiry)
                    self.assertFalse(self.consume(approval=candidate))
            db.execute(
                "UPDATE finance_key_approval_candidate SET expires_at=%s WHERE approval_id=%s",
                (self.approval.expires_at, self.approval.approval_id),
            )
        self.assertEqual(self.audit_count(), 0)
        self.assertTrue(self.consume())

    def test_unprivileged_database_role_cannot_read_or_modify_approvals(self):
        # The disposable CI administrator may create a synthetic NOLOGIN
        # role, but the role itself receives no approval or audit grants.
        from psycopg import sql
        role = "ci_approval_denied_" + uuid4().hex[:12]
        with psycopg.connect(self.dsn, autocommit=True) as db:
            db.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS").format(
                sql.Identifier(role)
            ))
            try:
                attempts = [
                    ("SELECT approval_id FROM finance_key_approval_candidate", ()),
                    ("UPDATE finance_key_approval_candidate SET consumed_at=now() WHERE approval_id=%s",
                     (self.approval.approval_id,)),
                    ("INSERT INTO finance_key_approval_audit_candidate (approval_id, action) VALUES (%s, 'consumed')",
                     (self.approval.approval_id,)),
                ]
                for statement, args in attempts:
                    with self.subTest(statement=statement):
                        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                            with db.transaction():
                                db.execute(sql.SQL("SET LOCAL ROLE {}").format(
                                    sql.Identifier(role)
                                ))
                                db.execute(statement, args)
            finally:
                db.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
        self.assertEqual(self.audit_count(), 0)
        self.assertTrue(self.consume())

    def test_consumed_audit_cannot_be_updated_deleted_or_truncated(self):
        self.assertTrue(self.consume())
        with psycopg.connect(self.dsn, autocommit=True) as db:
            attempts = [
                ("UPDATE finance_key_approval_audit_candidate SET action='consumed' WHERE approval_id=%s",
                 (self.approval.approval_id,)),
                ("DELETE FROM finance_key_approval_audit_candidate WHERE approval_id=%s",
                 (self.approval.approval_id,)),
                ("TRUNCATE finance_key_approval_audit_candidate", ()),
            ]
            for statement, values in attempts:
                with self.subTest(statement=statement):
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        db.execute(statement, values)
        self.assertEqual(self.audit_count(), 1)
        self.assertFalse(self.consume())

    def test_provisioning_cannot_overwrite_existing_approval(self):
        with psycopg.connect(self.dsn, autocommit=True) as db:
            with self.assertRaises(FinanceAccessDenied):
                provision_test_approval(
                    db, namespace=self.namespace, approval=self.approval
                )
        self.assertEqual(self.audit_count(), 0)


if __name__ == "__main__":
    unittest.main()
