"""Review-only offline OIDC JWT verifier using operator-pinned JWKS.

Keys must be supplied by separately trusted issuer config, never from token
header URLs or request input. Does not expose any finance API or grant tenant
membership. No live identity provider is configured by this candidate.
"""
import re
from membership_candidate import TrustedSubject
from tenant_access import FinanceAccessDenied, SUBJECT_RE

MAX_TOKEN_BYTES = 8192
KID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def verify_oidc_jwt(token: str, *, issuer: str, audience: str,
                    jwks: dict, leeway_seconds: int = 30,
                    expected_token_use: str = "access") -> TrustedSubject:
    """Validate pinned issuer, audience, RSA signature and time claims.

    The issuer, audience and JWKS arguments MUST be independently configured
    on the trusted server. Successful validation never authorizes a tenant;
    the caller must additionally resolve active server-side membership.
    """
    try:
        import jwt

        if (not isinstance(token, str) or not token or
                len(token.encode("utf-8")) > MAX_TOKEN_BYTES):
            raise ValueError("invalid token length")
        if (not isinstance(issuer, str) or not issuer.startswith("https://") or
                not isinstance(audience, str) or not audience or
                not isinstance(jwks, dict) or
                not isinstance(jwks.get("keys"), list) or
                len(jwks["keys"]) > 20 or not jwks["keys"]):
            raise ValueError("trusted issuer, audience and JWKS required")
        if (not isinstance(leeway_seconds, int) or
                isinstance(leeway_seconds, bool) or
                not 0 <= leeway_seconds <= 60):
            raise ValueError("invalid clock skew")
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256":
            raise ValueError("only RS256 is allowed")
        kid = header.get("kid")
        if not isinstance(kid, str) or not KID_RE.fullmatch(kid):
            raise ValueError("unrecognized key id")
        if any(x in header for x in ("jku", "jwk", "x5u")):
            raise ValueError("untrusted token key source")
        matching = [key for key in jwks["keys"]
                    if isinstance(key, dict) and key.get("kid") == kid and
                    key.get("kty") == "RSA" and
                    key.get("alg", "RS256") == "RS256" and
                    key.get("use", "sig") == "sig"]
        if len(matching) != 1:
            raise ValueError("missing or duplicate signing key")
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(matching[0])
        claims = jwt.decode(
            token, key=public_key, algorithms=["RS256"],
            issuer=issuer, audience=audience,
            leeway=leeway_seconds,
            options={
                "require": ["iss", "sub", "aud", "exp", "iat", "nbf"],
                "verify_signature": True, "verify_exp": True,
                "verify_iat": True, "verify_nbf": True,
                "verify_iss": True, "verify_aud": True,
            },
        )
        # This candidate requires a separately configured access-token profile.
        # A signed ID token is identity evidence for an OAuth client, not a
        # finance API access token. Provider-specific token types still need
        # review before selecting an identity provider.
        if expected_token_use != "access" or claims.get("token_use") != "access":
            raise ValueError("not an access token")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not SUBJECT_RE.fullmatch(subject):
            raise ValueError("invalid subject")
        return TrustedSubject(subject)
    except Exception:
        # Do not surface token claims, key details or JWT error strings.
        raise FinanceAccessDenied("Finance access denied") from None
