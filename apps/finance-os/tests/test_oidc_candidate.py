"""Offline signed JWT tests using ephemeral RSA test keys, no network."""
import base64
import json
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    CRYPTO_READY = True
except ImportError:
    CRYPTO_READY = False
from tenant_access import FinanceAccessDenied
from oidc_candidate import verify_oidc_jwt


@unittest.skipUnless(CRYPTO_READY, "PyJWT and cryptography required")
class OidcCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CRYPTO_READY:
            return
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.bad_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.issuer = "https://issuer.example.test"
        cls.audience = "core8-finance-ci"
        public = cls.key.public_key().public_numbers()
        def b64(x):
            return base64.urlsafe_b64encode(x.to_bytes((x.bit_length()+7)//8, "big")).rstrip(b"=").decode()
        cls.jwks = {"keys": [{"kty": "RSA", "kid": "ci-key", "alg": "RS256", "use": "sig",
                               "n": b64(public.n), "e": b64(public.e)}]}

    def claims(self):
        now = int(time.time())
        return {"sub": "sub_test_123", "iss": self.issuer, "aud": self.audience,
                "iat": now, "nbf": now, "exp": now+300, "token_use": "access"}

    def signed(self, claims=None, key=None, headers=None, algorithm="RS256"):
        return jwt.encode(claims if claims is not None else self.claims(),
                          self.key if key is None else key, algorithm=algorithm,
                          headers={"kid":"ci-key", **(headers or {})})

    def verify(self, token, **kwargs):
        return verify_oidc_jwt(token, issuer=kwargs.get("issuer", self.issuer),
                               audience=kwargs.get("audience", self.audience),
                               jwks=kwargs.get("jwks", self.jwks),
                               leeway_seconds=0)

    def test_valid_signed_subject(self):
        self.assertEqual(self.verify(self.signed()).value, "sub_test_123")

    def test_reject_issuer_audience_signature_and_expiration(self):
        now = int(time.time())
        cases = [
            self.signed({**self.claims(), "iss":"https://evil.example.test"}),
            self.signed({**self.claims(), "aud":"other-audience"}),
            self.signed({**self.claims(), "exp":now-90}),
            self.signed({**self.claims(), "nbf":now+90}),
            self.signed({**self.claims(), "iat":now+90}),
            self.signed(key=self.bad_key),
            self.signed({k:v for k,v in self.claims().items() if k != "exp"}),
            self.signed({**self.claims(), "sub":"bad subject"}),
        ]
        for token in cases:
            with self.subTest(token=token[:10]):
                with self.assertRaises(FinanceAccessDenied):
                    self.verify(token)

    def test_id_token_cannot_be_reused_as_finance_access_token(self):
        # A valid signature, issuer and audience are insufficient when the
        # token was issued as an ID token rather than an access token.
        for claims in (
            {**self.claims(), "token_use": "id"},
            {k: v for k, v in self.claims().items() if k != "token_use"},
            {**self.claims(), "token_use": ["access"]},
        ):
            with self.subTest(token_use=claims.get("token_use")):
                with self.assertRaises(FinanceAccessDenied):
                    self.verify(self.signed(claims))

    def test_verified_token_still_requires_active_tenant_membership(self):
        from membership_candidate import resolve_finance_membership
        from tenant_access import require_finance_permission

        class FakeMembershipDB:
            def __init__(self, role, enabled):
                self.role, self.enabled = role, enabled
                self.params = None

            def execute(self, sql, params):
                self.params = params
                return self

            def fetchall(self):
                return [(self.role, self.enabled)]

        subject = self.verify(self.signed())
        inactive = FakeMembershipDB("operator", False)
        with self.assertRaises(FinanceAccessDenied):
            resolve_finance_membership(inactive, subject=subject,
                                       tenant_id="tenant_alpha")
        active = FakeMembershipDB("viewer", True)
        principal = resolve_finance_membership(active, subject=subject,
                                                tenant_id="tenant_alpha")
        self.assertEqual(active.params, ("sub_test_123", "tenant_alpha"))
        require_finance_permission(principal, tenant_id="tenant_alpha",
                                   action="finance:read")
        with self.assertRaises(FinanceAccessDenied):
            require_finance_permission(principal, tenant_id="tenant_beta",
                                       action="finance:read")
        with self.assertRaises(FinanceAccessDenied):
            require_finance_permission(principal, tenant_id="tenant_alpha",
                                       action="finance:operate")

    def test_reject_untrusted_header_key_urls_and_key_mismatch(self):
        for headers in ({"jku":"https://evil.example.test/key"},
                        {"x5u":"https://evil.example.test/cert"},
                        {"kid":"different-key"}):
            with self.subTest(headers=headers):
                with self.assertRaises(FinanceAccessDenied):
                    self.verify(self.signed(headers=headers))

    def test_reject_hmac_algorithm_substitution(self):
        token = jwt.encode(self.claims(), "ci-HMAC", algorithm="HS256",
                           headers={"kid":"ci-key"})
        with self.assertRaises(FinanceAccessDenied):
            self.verify(token)

    def test_reject_duplicate_or_unpinned_keys(self):
        with self.assertRaises(FinanceAccessDenied):
            self.verify(self.signed(), jwks={"keys":self.jwks["keys"]*2})
        with self.assertRaises(FinanceAccessDenied):
            self.verify(self.signed(), jwks={"keys":[]})

    def test_reject_excessive_lifetime_and_bad_time_types(self):
        now = int(time.time())
        for claims in (
            {**self.claims(), "exp": now + 7200},
            {**self.claims(), "exp": now},
            {**self.claims(), "iat": True},
            {**self.claims(), "nbf": "0"},
            {**self.claims(), "exp": float(now + 300)},
            {**self.claims(), "nbf": now + 400, "exp": now + 200},
        ):
            with self.subTest(claims=claims):
                with self.assertRaises(FinanceAccessDenied):
                    self.verify(self.signed(claims))

    def test_reject_unsafe_issuer_and_critical_jwt_headers(self):
        for issuer in (
            "https://issuer.example.test@evil.example.test",
            "https://issuer.example.test?override=true",
            "https://issuer.example.test#fragment",
            "https://",
            "http://issuer.example.test",
        ):
            with self.subTest(issuer=issuer):
                with self.assertRaises(FinanceAccessDenied):
                    self.verify(self.signed(), issuer=issuer)
        with self.assertRaises(FinanceAccessDenied):
            self.verify(self.signed(headers={"crit": ["b64"]}))

    def test_reject_weak_rsa_signing_key(self):
        weak = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        public = weak.public_key().public_numbers()
        def b64(value):
            return base64.urlsafe_b64encode(
                value.to_bytes((value.bit_length() + 7) // 8, "big")
            ).rstrip(b"=").decode()
        jwks = {"keys": [{
            "kty": "RSA", "kid": "weak-ci", "use": "sig", "alg": "RS256",
            "n": b64(public.n), "e": b64(public.e),
        }]}
        token = self.signed(key=weak, headers={"kid": "weak-ci"})
        with self.assertRaises(FinanceAccessDenied):
            self.verify(token, jwks=jwks)

    def test_pinned_key_rotation_and_emergency_revocation(self):
        # The JWKS is supplied by a trusted operator, never fetched from token URLs.
        # During an approved overlap, either pinned key can verify its own JWT.
        rotated_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub = rotated_key.public_key().public_numbers()
        def b64(value):
            return base64.urlsafe_b64encode(
                value.to_bytes((value.bit_length() + 7) // 8, "big")
            ).rstrip(b"=").decode()
        new_jwk = {
            "kty": "RSA", "kid": "ci-rotated", "alg": "RS256", "use": "sig",
            "n": b64(pub.n), "e": b64(pub.e),
        }
        old_token = self.signed()
        new_token = self.signed(key=rotated_key, headers={"kid": "ci-rotated"})
        overlap = {"keys": [*self.jwks["keys"], new_jwk]}
        self.assertEqual(self.verify(old_token, jwks=overlap).value, "sub_test_123")
        self.assertEqual(self.verify(new_token, jwks=overlap).value, "sub_test_123")
        # After removal of the compromised/retired key, its token fails
        # regardless of the JWT's remaining expiry window.
        active = {"keys": [new_jwk]}
        self.assertEqual(self.verify(new_token, jwks=active).value, "sub_test_123")
        with self.assertRaises(FinanceAccessDenied):
            self.verify(old_token, jwks=active)
        with self.assertRaises(FinanceAccessDenied):
            self.verify(new_token, jwks=self.jwks)

    def test_duplicate_key_id_and_token_supplied_jwk_denied(self):
        rotated_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub = rotated_key.public_key().public_numbers()
        def b64(value):
            return base64.urlsafe_b64encode(
                value.to_bytes((value.bit_length() + 7) // 8, "big")
            ).rstrip(b"=").decode()
        ambiguous = {"keys": [*self.jwks["keys"], {
            "kty": "RSA", "kid": "ci-key", "alg": "RS256", "use": "sig",
            "n": b64(pub.n), "e": b64(pub.e)
        }]}
        with self.assertRaises(FinanceAccessDenied):
            self.verify(self.signed(), jwks=ambiguous)
        with self.assertRaises(FinanceAccessDenied):
            self.verify(self.signed(headers={"jwk": self.jwks["keys"][0]}))

    def test_reject_missing_configuration_and_oversized_token(self):
        with self.assertRaises(FinanceAccessDenied):
            self.verify(self.signed(), issuer="http://insecure")
        with self.assertRaises(FinanceAccessDenied):
            self.verify("x"*9000)

if __name__ == "__main__":
    unittest.main()
