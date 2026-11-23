"""Signed registry snapshot recovery tests with synthetic RSA keys and no I/O."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from cryptography.hazmat.primitives.asymmetric import rsa
    READY = True
except ImportError:
    READY = False
from tenant_access import FinanceAccessDenied
from pinned_jwks_candidate import PinnedJwksRegistry
from jwks_state_candidate import export_registry_state, import_registry_state
from test_pinned_jwks_candidate import PinnedJwksCandidateTests


@unittest.skipUnless(READY, "cryptography required")
class SignedJwksRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.secret = b"synthetic-ci-authorization-key-only-32bytes-min"
        self.first = PinnedJwksCandidateTests.jwk(
            rsa.generate_private_key(public_exponent=65537, key_size=2048), "first"
        )
        self.second = PinnedJwksCandidateTests.jwk(
            rsa.generate_private_key(public_exponent=65537, key_size=2048), "second"
        )
        self.registry = PinnedJwksRegistry({"keys": [self.first]})

    def save(self):
        return export_registry_state(self.registry, signing_key=self.secret)

    def load(self, blob, floor):
        return import_registry_state(
            blob, signing_key=self.secret, minimum_generation=floor
        )

    def test_snapshot_recovery_preserves_retired_key_tombstone(self):
        old = self.save()
        self.registry.replace({"keys": [self.first, self.second]}, generation=2)
        self.registry.replace({"keys": [self.second]}, generation=3)
        latest = self.save()
        restored = self.load(latest, 3)
        self.assertEqual(restored.snapshot()[0], 3)
        with self.assertRaises(FinanceAccessDenied):
            restored.replace({"keys": [self.first, self.second]}, generation=4)
        with self.assertRaises(FinanceAccessDenied):
            self.load(old, 3)
        self.assertEqual(restored.snapshot()[1]["keys"][0]["kid"], "second")

    def test_reject_tampering_wrong_secret_and_missing_floor(self):
        blob = self.save()
        for candidate in (blob[:-8] + b"tampered!", b"", blob + b"extra"):
            with self.subTest(candidate=candidate[:20]):
                with self.assertRaises(FinanceAccessDenied):
                    self.load(candidate, 1)
        with self.assertRaises(FinanceAccessDenied):
            import_registry_state(
                blob, signing_key=b"another-synthetic-strong-signing-key-32",
                minimum_generation=1
            )
        for floor in (None, 0, "1", True, 2):
            with self.subTest(floor=floor):
                with self.assertRaises(FinanceAccessDenied):
                    self.load(blob, floor)

    def test_reject_signed_snapshot_with_active_retired_overlap(self):
        # Even a hypothetically trusted signer cannot produce an invalid state.
        import base64
        import hashlib
        import hmac
        blob = self.save()
        parsed = json.loads(blob)
        parsed["state"]["retired"] = ["first"]
        raw = json.dumps(parsed["state"], sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("ascii")
        parsed["mac"] = base64.urlsafe_b64encode(
            hmac.new(self.secret, raw, hashlib.sha256).digest()
        ).decode("ascii")
        malformed = json.dumps(parsed, separators=(",", ":")).encode("ascii")
        with self.assertRaises(FinanceAccessDenied):
            self.load(malformed, 1)

    def test_missing_or_weak_export_signing_key_denied(self):
        for key in (None, b"short", "", 123):
            with self.subTest(key=key):
                with self.assertRaises(FinanceAccessDenied):
                    export_registry_state(self.registry, signing_key=key)


if __name__ == "__main__":
    unittest.main()
