"""Disposable PostgreSQL audit keyring snapshot CAS and restore regressions."""
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

from audit_key_rotation_candidate import AuditKeyringCandidate, PinnedAuditKey
from audit_keyring_store_candidate import (
    initialize_audit_keyring_store, recover_audit_keyring_store,
    advance_audit_keyring_store,
)
from tenant_access import FinanceAccessDenied

MAC = b"synthetic-test-metadata-mac-key-32bytes-minimum"
OLD = PinnedAuditKey("store_old", b"synthetic-old-audit-signing-key-material-over-32")
NEW = PinnedAuditKey("store_new", b"synthetic-new-audit-signing-key-material-over-32")
OTHER = PinnedAuditKey("store_other", b"synthetic-other-audit-signing-key-over-32")
MATERIAL = {k.kid: k.secret for k in (OLD, NEW, OTHER)}


@unittest.skipUnless(READY, "requires explicitly disposable PostgreSQL test DB")
class AuditKeyringStorePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not READY:
            return
        cls.dsn = os.environ["DATABASE_URL"]
        source = (Path(__file__).resolve().parents[1] / "sql" /
                  "audit_keyring_store_candidate.sql").read_text()
        with psycopg.connect(cls.dsn) as db:
            db.execute(source)

    @classmethod
    def tearDownClass(cls):
        if READY:
            with psycopg.connect(cls.dsn) as db:
                db.execute("DROP TABLE IF EXISTS finance_audit_keyring_store_candidate")

    def setUp(self):
        self.namespace = "ci_audit_store_" + uuid4().hex[:12]
        with psycopg.connect(self.dsn, autocommit=True) as db:
            initialize_audit_keyring_store(
                db, namespace=self.namespace,
                registry=AuditKeyringCandidate(active=OLD),
                signing_key=MAC,
            )

    def tearDown(self):
        with psycopg.connect(self.dsn) as db:
            db.execute(
                "DELETE FROM finance_audit_keyring_store_candidate WHERE namespace=%s",
                (self.namespace,),
            )

    def restore(self, generation):
        with psycopg.connect(self.dsn, autocommit=True) as db:
            return recover_audit_keyring_store(
                db, namespace=self.namespace, signing_key=MAC,
                external_generation=generation,
                trusted_key_material=MATERIAL,
            )

    def advance(self, next_key, *, retain=(), generation=1):
        ring = self.restore(generation)
        ring.rotate(expected_generation=generation, new_active=next_key,
                    retain=retain)
        with psycopg.connect(self.dsn, autocommit=True) as db:
            return advance_audit_keyring_store(
                db, namespace=self.namespace, signing_key=MAC,
                expected_generation=generation, external_generation=generation + 1,
                new_registry=ring, trusted_key_material=MATERIAL,
            )

    def test_restart_revocation_and_stale_floor_denied(self):
        self.assertEqual(self.restore(1).active_kid, OLD.kid)
        self.assertEqual(self.advance(NEW, retain=(OLD.kid,)), 2)
        self.assertEqual(self.advance(NEW, generation=2), 3)
        reopened = self.restore(3)
        self.assertEqual(reopened.active_kid, NEW.kid)
        with self.assertRaises(FinanceAccessDenied):
            reopened.rotate(expected_generation=3, new_active=OLD)
        with self.assertRaises(FinanceAccessDenied):
            self.restore(2)
        with self.assertRaises(FinanceAccessDenied):
            self.restore(4)

    def test_concurrent_competing_writers_one_wins(self):
        barrier = threading.Barrier(2)
        def attempt(key):
            ring = self.restore(1)
            ring.rotate(expected_generation=1, new_active=key, retain=(OLD.kid,))
            barrier.wait(timeout=10)
            try:
                with psycopg.connect(self.dsn, autocommit=True) as db:
                    advance_audit_keyring_store(
                        db, namespace=self.namespace, signing_key=MAC,
                        expected_generation=1, external_generation=2,
                        new_registry=ring, trusted_key_material=MATERIAL,
                    )
                return "committed"
            except FinanceAccessDenied:
                return "stale"
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, (NEW, OTHER)))
        self.assertCountEqual(results, ["committed", "stale"])
        self.assertIn(self.restore(2).active_kid, (NEW.kid, OTHER.kid))

    def test_signed_row_tampering_and_old_row_restore_denied(self):
        with psycopg.connect(self.dsn, autocommit=True) as db:
            old_gen, old_blob = db.execute(
                "SELECT generation, signed_snapshot FROM finance_audit_keyring_store_candidate WHERE namespace=%s",
                (self.namespace,),
            ).fetchone()
        self.advance(NEW)
        with psycopg.connect(self.dsn, autocommit=True) as db:
            db.execute(
                """UPDATE finance_audit_keyring_store_candidate
                   SET generation=%s, signed_snapshot=%s WHERE namespace=%s""",
                (old_gen, old_blob, self.namespace),
            )
        with self.assertRaises(FinanceAccessDenied):
            self.restore(2)
        with psycopg.connect(self.dsn, autocommit=True) as db:
            db.execute(
                """UPDATE finance_audit_keyring_store_candidate
                   SET generation=2, signed_snapshot=%s WHERE namespace=%s""",
                (b"corrupt", self.namespace),
            )
        with self.assertRaises(FinanceAccessDenied):
            self.restore(2)

    def test_invalid_transition_and_reused_key_material_fail_closed(self):
        ring = self.restore(1)
        ring.rotate(expected_generation=1, new_active=NEW)
        with psycopg.connect(self.dsn, autocommit=True) as db:
            for generation in (1, 3, True):
                with self.subTest(generation=generation):
                    with self.assertRaises(FinanceAccessDenied):
                        advance_audit_keyring_store(
                            db, namespace=self.namespace, signing_key=MAC,
                            expected_generation=1, external_generation=generation,
                            new_registry=ring, trusted_key_material=MATERIAL,
                        )
            with self.assertRaises(FinanceAccessDenied):
                initialize_audit_keyring_store(
                    db, namespace=self.namespace,
                    registry=AuditKeyringCandidate(active=OLD),
                    signing_key=MAC,
                )
            with db.transaction():
                with self.assertRaises(FinanceAccessDenied):
                    advance_audit_keyring_store(
                        db, namespace=self.namespace, signing_key=MAC,
                        expected_generation=1, external_generation=2,
                        new_registry=ring, trusted_key_material=MATERIAL,
                    )
        self.assertEqual(self.restore(1).active_kid, OLD.kid)


if __name__ == "__main__":
    unittest.main()
