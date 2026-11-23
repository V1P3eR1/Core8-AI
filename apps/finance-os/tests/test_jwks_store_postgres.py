"""Real disposable PostgreSQL persistence/restore and CAS tests.

Never runs without APP_ENV=test and an explicitly supplied test DATABASE_URL.
Synthetic RSA keys and isolated table only; no provider or finance endpoint.
"""
import base64
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
    from cryptography.hazmat.primitives.asymmetric import rsa
    READY = os.getenv("APP_ENV") == "test" and bool(os.getenv("DATABASE_URL"))
except ImportError:
    READY = False

from tenant_access import FinanceAccessDenied
from jwks_store_candidate import (
    initialize_jwks_store, recover_jwks_store, rotate_jwks_store,
)

SECRET = b"test-only-synthetic-state-signing-key-at-least-32-bytes"
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(READY, "disposable CI PostgreSQL and crypto required")
class JwksStorePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not READY:
            return
        cls.dsn = os.environ["DATABASE_URL"]
        source = (ROOT / "sql" / "jwks_store_candidate.sql").read_text()
        with psycopg.connect(cls.dsn) as db:
            for statement in source.split(";"):
                clean = "\n".join(
                    line for line in statement.splitlines()
                    if not line.lstrip().startswith("--")
                ).strip()
                if clean:
                    db.execute(clean)

    @classmethod
    def tearDownClass(cls):
        if not READY:
            return
        with psycopg.connect(cls.dsn) as db:
            db.execute("DROP TABLE IF EXISTS finance_jwks_store_candidate")

    @staticmethod
    def public_jwk(kid):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        values = key.public_key().public_numbers()
        def b64(i):
            return base64.urlsafe_b64encode(
                i.to_bytes((i.bit_length() + 7) // 8, "big")
            ).rstrip(b"=").decode()
        return {
            "kid": kid, "kty": "RSA", "alg": "RS256", "use": "sig",
            "n": b64(values.n), "e": b64(values.e),
        }

    def setUp(self):
        self.namespace = "ci_jwks_" + uuid4().hex
        self.old = self.public_jwk("old")
        self.new = self.public_jwk("new")
        with psycopg.connect(self.dsn, autocommit=True) as db:
            initialize_jwks_store(
                db, namespace=self.namespace, jwks={"keys": [self.old]},
                signing_key=SECRET,
            )

    def tearDown(self):
        with psycopg.connect(self.dsn) as db:
            db.execute(
                "DELETE FROM finance_jwks_store_candidate WHERE namespace=%s",
                (self.namespace,),
            )

    def recover(self, floor=1):
        with psycopg.connect(self.dsn, autocommit=True) as db:
            return recover_jwks_store(
                db, namespace=self.namespace, signing_key=SECRET,
                minimum_generation=floor,
            )

    def rotate(self, expected, proposed, floor=1, retire=()):
        with psycopg.connect(self.dsn, autocommit=True) as db:
            return rotate_jwks_store(
                db, namespace=self.namespace, signing_key=SECRET,
                minimum_generation=floor, expected_generation=expected,
                proposed_jwks={"keys": proposed}, retire=retire,
            )

    def test_restart_recovery_preserves_revoked_key_and_cas(self):
        self.assertEqual(self.recover().snapshot()[0], 1)
        self.assertEqual(self.rotate(1, [self.old, self.new]), 2)
        self.assertEqual(self.rotate(2, [self.new], floor=2), 3)
        restored = self.recover(floor=3)  # independent new connection
        self.assertEqual(restored.snapshot()[0], 3)
        self.assertEqual(restored.snapshot()[1]["keys"][0]["kid"], "new")
        with self.assertRaises(FinanceAccessDenied):
            restored.replace({"keys": [self.old, self.new]}, generation=4)
        with self.assertRaises(FinanceAccessDenied):
            self.rotate(3, [self.old, self.new], floor=3)
        with self.assertRaises(FinanceAccessDenied):
            self.rotate(2, [self.new], floor=3)
        with self.assertRaises(FinanceAccessDenied):
            self.recover(floor=4)

    def test_concurrent_competing_writers_only_one_wins(self):
        contender = self.public_jwk("other")
        barrier = threading.Barrier(2)
        def attempt(new_jwk):
            barrier.wait(timeout=5)
            try:
                self.rotate(1, [new_jwk])
                return "committed"
            except FinanceAccessDenied:
                return "stale"
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [pool.submit(attempt, key) for key in (self.new, contender)]
            results = [task.result(timeout=15) for task in tasks]
        self.assertCountEqual(results, ["committed", "stale"])
        _, jwks = self.recover(floor=2).snapshot()
        self.assertEqual(len(jwks["keys"]), 1)
        self.assertIn(jwks["keys"][0]["kid"], {"new", "other"})

    def test_transaction_rollback_and_signed_tampering_denied(self):
        with psycopg.connect(self.dsn, autocommit=True) as db:
            with self.assertRaisesRegex(RuntimeError, "simulate crash"):
                with db.transaction():
                    rotate_jwks_store(
                        db, namespace=self.namespace, signing_key=SECRET,
                        minimum_generation=1, expected_generation=1,
                        proposed_jwks={"keys": [self.new]},
                    )
                    raise RuntimeError("simulate crash")
        self.assertEqual(self.recover().snapshot()[0], 1)
        with psycopg.connect(self.dsn, autocommit=True) as db:
            db.execute(
                """UPDATE finance_jwks_store_candidate
                   SET signed_snapshot=%s WHERE namespace=%s""",
                (b"tampered-but-database-generation-unchanged", self.namespace),
            )
        with self.assertRaises(FinanceAccessDenied):
            self.recover()

    def test_bootstrap_cannot_overwrite_existing_registry(self):
        with psycopg.connect(self.dsn, autocommit=True) as db:
            with self.assertRaises(FinanceAccessDenied):
                initialize_jwks_store(
                    db, namespace=self.namespace, jwks={"keys": [self.new]},
                    signing_key=SECRET,
                )
        self.assertEqual(self.recover().snapshot()[1]["keys"][0]["kid"], "old")


if __name__ == "__main__":
    unittest.main()
