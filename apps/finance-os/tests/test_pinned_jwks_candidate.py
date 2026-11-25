"""Offline pinned JWKS lifecycle tests with ephemeral RSA keys."""
import base64
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    READY = True
except ImportError:
    READY = False
from pinned_jwks_candidate import PinnedJwksRegistry
from oidc_candidate import verify_oidc_jwt
from tenant_access import FinanceAccessDenied


@unittest.skipUnless(READY, "PyJWT[crypto] required")
class PinnedJwksCandidateTests(unittest.TestCase):
    def setUp(self):
        self.first = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.second = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.old = self.jwk(self.first, "first")
        self.new = self.jwk(self.second, "second")
        self.registry = PinnedJwksRegistry({"keys": [self.old]})

    @staticmethod
    def jwk(key, kid):
        numbers = key.public_key().public_numbers()
        def encode(i):
            return base64.urlsafe_b64encode(
                i.to_bytes((i.bit_length() + 7) // 8, "big")
            ).rstrip(b"=").decode()
        return {"kty": "RSA", "kid": kid, "alg": "RS256",
                "use": "sig", "n": encode(numbers.n), "e": encode(numbers.e)}

    @staticmethod
    def token(key, kid):
        import time
        now = int(time.time())
        return jwt.encode({
            "iss": "https://ci.example.test", "aud": "finance-ci",
            "sub": "user_test", "iat": now, "nbf": now, "exp": now + 120,
            "token_use": "access",
        }, key, algorithm="RS256", headers={"kid": kid})

    @staticmethod
    def verify(token, registry):
        _, jwks = registry.snapshot()
        return verify_oidc_jwt(
            token, issuer="https://ci.example.test",
            audience="finance-ci", jwks=jwks, leeway_seconds=0
        )

    def test_overlap_retire_prevents_reintroduction_and_revokes_token(self):
        old = self.token(self.first, "first")
        new = self.token(self.second, "second")
        self.assertEqual(self.verify(old, self.registry).value, "user_test")
        self.registry.replace({"keys": [self.old, self.new]}, generation=2)
        self.assertEqual(self.verify(old, self.registry).value, "user_test")
        self.assertEqual(self.verify(new, self.registry).value, "user_test")
        self.registry.replace({"keys": [self.new]}, generation=3)
        with self.assertRaises(FinanceAccessDenied):
            self.verify(old, self.registry)
        self.assertEqual(self.verify(new, self.registry).value, "user_test")
        with self.assertRaises(FinanceAccessDenied):
            self.registry.replace({"keys": [self.old, self.new]}, generation=4)
        self.assertEqual(self.registry.snapshot()[0], 3)

    def test_stale_generation_and_same_kid_replacement_denied_atomically(self):
        before = self.registry.snapshot()
        with self.assertRaises(FinanceAccessDenied):
            self.registry.replace({"keys": [self.new]}, generation=1)
        with self.assertRaises(FinanceAccessDenied):
            self.registry.replace(
                {"keys": [self.jwk(self.second, "first")]}, generation=2
            )
        self.assertEqual(self.registry.snapshot(), before)

    def test_detached_snapshot_cannot_modify_active_registry(self):
        generation, snapshot = self.registry.snapshot()
        snapshot["keys"][0]["kid"] = "evil"
        snapshot["keys"].clear()
        self.assertEqual(generation, 1)
        self.assertEqual(self.registry.snapshot()[1]["keys"][0]["kid"], "first")

    def test_malformed_keys_and_private_components_fail_closed(self):
        for key in (
            {**self.old, "d": "secret"}, {**self.old, "alg": "HS256"},
            {**self.old, "use": "enc"}, {**self.old, "jku": "https://attacker.test"},
        ):
            with self.subTest(key=key.get("alg"), extra=sorted(key)):
                with self.assertRaises(FinanceAccessDenied):
                    PinnedJwksRegistry({"keys": [key]})
        with self.assertRaises(FinanceAccessDenied):
            PinnedJwksRegistry({"keys": [self.old, self.old]})
        with self.assertRaises(FinanceAccessDenied):
            self.registry.replace({"keys": [self.old]}, generation=2, retire=["first"])

    def test_preflight_does_not_change_generation_or_tombstones(self):
        before = self.registry.snapshot()
        self.assertTrue(
            self.registry.preview_replace(
                {"keys": [self.old, self.new]}, generation=2
            )
        )
        self.assertEqual(self.registry.snapshot(), before)
        with self.assertRaises(FinanceAccessDenied):
            self.registry.preview_replace(
                {"keys": [self.old]}, generation=2, retire=("first",)
            )
        self.assertEqual(self.registry.snapshot(), before)
        self.assertEqual(
            self.registry.replace(
                {"keys": [self.old, self.new]}, generation=2
            ), 2
        )
        self.registry.replace({"keys": [self.new]}, generation=3)
        retired_state = self.registry.snapshot()
        with self.assertRaises(FinanceAccessDenied):
            self.registry.preview_replace(
                {"keys": [self.old, self.new]}, generation=4
            )
        self.assertEqual(self.registry.snapshot(), retired_state)

    def test_unknown_or_stale_approval_input_denied(self):
        for generation in (0, -1, True, "2", 1):
            with self.subTest(generation=generation):
                with self.assertRaises(FinanceAccessDenied):
                    self.registry.replace({"keys": [self.old]}, generation=generation)
        self.assertEqual(self.registry.snapshot()[0], 1)


if __name__ == "__main__":
    unittest.main()
