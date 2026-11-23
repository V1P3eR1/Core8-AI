"""Review-only in-memory, operator-controlled pinned JWKS lifecycle.

NOT a provider JWKS fetcher, persistent key store, secrets manager, or deployed
authorization service. The caller must independently authenticate/authorize the
operator and persist approved generations securely outside this candidate.
A process restart resets this object; do not use it in production.
"""
from copy import deepcopy
from threading import RLock

from oidc_candidate import KID_RE
from tenant_access import FinanceAccessDenied

_MAX_KEYS = 20
_PRIVATE_FIELDS = frozenset({"d", "p", "q", "dp", "dq", "qi", "oth", "k"})


def _validate_public_keys(jwks):
    """Validate entire trusted JWKS before changing state; do not allow private keys."""
    try:
        import jwt
        if (type(jwks) is not dict or type(jwks.get("keys")) is not list or
                not 0 < len(jwks["keys"]) <= _MAX_KEYS):
            raise ValueError("invalid public key set")
        keys, ids = {}, set()
        for key in jwks["keys"]:
            if type(key) is not dict or any(k in key for k in _PRIVATE_FIELDS):
                raise ValueError("private or malformed JWK")
            kid = key.get("kid")
            if (type(kid) is not str or not KID_RE.fullmatch(kid) or
                    kid in ids or key.get("kty") != "RSA" or
                    key.get("alg") != "RS256" or key.get("use") != "sig" or
                    set(key) - {"kid", "kty", "alg", "use", "n", "e"}):
                raise ValueError("unsupported key parameters")
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
            if public_key.key_size < 2048:
                raise ValueError("weak RSA key")
            ids.add(kid)
            keys[kid] = deepcopy(key)
        return keys
    except Exception:
        raise FinanceAccessDenied("Finance key configuration denied") from None


class PinnedJwksRegistry:
    """Atomic local-only snapshots and irreversible retired-key tombstones.

    Generation is a monotonic integer supplied by an approved operator. The
    registry does NOT authenticate that operator and provides no persistence.
    """

    def __init__(self, jwks, *, generation=1):
        if type(generation) is not int or generation < 1:
            raise FinanceAccessDenied("Finance key configuration denied")
        self._lock = RLock()
        self._keys = _validate_public_keys(jwks)
        self._generation = generation
        self._retired = set()

    def snapshot(self):
        """Return a detached, read-only-in-practice copy for JWT verification."""
        with self._lock:
            return self._generation, {"keys": deepcopy(list(self._keys.values()))}

    def preview_replace(self, jwks, *, generation, retire=()):
        """Validate a proposed transition without changing active keys.

        This is a preflight only; callers MUST validate again at commit time.
        The independent watermark must never be advanced for invalid input.
        """
        with self._lock:
            candidate = PinnedJwksRegistry(
                {"keys": deepcopy(list(self._keys.values()))},
                generation=self._generation,
            )
            candidate._retired = set(self._retired)
            candidate.replace(jwks, generation=generation, retire=retire)
        return True

    def replace(self, jwks, *, generation, retire=()):
        """Apply fully prevalidated next generation, or leave state untouched.

        Removing a key retires it permanently within this process, preventing
        rollback/reintroduction. An approved overlapping key remains active.
        """
        proposed = _validate_public_keys(jwks)
        if type(generation) is not int or type(retire) not in (tuple, list, frozenset):
            raise FinanceAccessDenied("Finance key configuration denied")
        if any(type(k) is not str for k in retire):
            raise FinanceAccessDenied("Finance key configuration denied")
        with self._lock:
            if generation <= self._generation:
                raise FinanceAccessDenied("Finance key configuration denied")
            old_ids = set(self._keys)
            retired = self._retired | (old_ids - set(proposed)) | set(retire)
            if set(proposed) & retired:
                raise FinanceAccessDenied("Finance key configuration denied")
            # Reusing an active kid with different key material is forbidden:
            # signing keys rotate by changing kid, never silently replacing it.
            for kid in old_ids & set(proposed):
                if proposed[kid] != self._keys[kid]:
                    raise FinanceAccessDenied("Finance key configuration denied")
            self._keys = proposed
            self._retired = retired
            self._generation = generation
            return self._generation
