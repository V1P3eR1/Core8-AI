"""Sandbox-only coordination against an INDEPENDENT anti-rollback watermark.

This module deliberately does not implement a durable external store. It
requires a trusted, independently administered floor service with linearizable
compare-and-swap. The watermark is advanced BEFORE the PostgreSQL mutation;
a subsequent database failure deliberately leaves a fail-closed mismatch
requiring an audited, manual recovery. Never reset the floor to repair it.

Do not pass a request-controlled watermark, tenant header or generic untrusted
object into the coordinator. No HTTP handler imports this module.
"""
from jwks_store_candidate import recover_jwks_store, rotate_jwks_store
from tenant_access import FinanceAccessDenied


class IndependentGenerationFloor:
    """Abstract trust contract, not a working floor service.

    A production implementation must authorize the caller, persist updates
    independently of the finance PostgreSQL failure domain, and guarantee a
    linearizable compare-and-swap. No production implementation is included.
    """

    def read(self, namespace):
        raise NotImplementedError

    def compare_and_advance(self, namespace, expected_generation, next_generation):
        raise NotImplementedError


def _floor_value(floor, namespace):
    if not isinstance(floor, IndependentGenerationFloor):
        raise FinanceAccessDenied("Finance key configuration denied")
    try:
        generation = floor.read(namespace)
        if type(generation) is not int or generation < 1:
            raise ValueError("invalid external generation")
        return generation
    except Exception:
        raise FinanceAccessDenied("Finance key configuration denied") from None


def recover_with_external_floor(conn, *, namespace, signing_key, floor):
    """Reject database snapshots older than the independent trusted floor."""
    generation = _floor_value(floor, namespace)
    return recover_jwks_store(
        conn, namespace=namespace, signing_key=signing_key,
        minimum_generation=generation,
    )


def rotate_with_external_floor(conn, *, namespace, signing_key, floor,
                               expected_generation, proposed_jwks, retire=()):
    """Advance independent floor before the DB write; never fail open.

    Floor CAS failure blocks rotation. If PostgreSQL fails after floor CAS,
    readers reject the older DB snapshot; a human-approved recovery process
    must resolve the mismatch without lowering the external floor. This
    intentionally prioritizes key revocation safety over availability.
    """
    if type(expected_generation) is not int or expected_generation < 1:
        raise FinanceAccessDenied("Finance key configuration denied")
    current = _floor_value(floor, namespace)
    if current != expected_generation:
        raise FinanceAccessDenied("Finance key configuration denied")
    # Confirm current signed DB snapshot before advancing the floor.
    registry = recover_jwks_store(
        conn, namespace=namespace, signing_key=signing_key,
        minimum_generation=current,
    )
    if registry.snapshot()[0] != current:
        raise FinanceAccessDenied("Finance key configuration denied")
    # Preflight before touching the independent high-watermark. An invalid
    # JWK, retired kid or malformed retirement list must not permanently
    # strand the database behind an otherwise unnecessary floor advance.
    # The transactional database writer independently validates again.
    registry.preview_replace(
        proposed_jwks, generation=expected_generation + 1, retire=retire
    )
    try:
        advanced = floor.compare_and_advance(
            namespace, expected_generation, expected_generation + 1
        )
    except Exception:
        raise FinanceAccessDenied("Finance key configuration denied") from None
    if advanced is not True:
        raise FinanceAccessDenied("Finance key configuration denied")
    return rotate_jwks_store(
        conn, namespace=namespace, signing_key=signing_key,
        minimum_generation=current, expected_generation=expected_generation,
        proposed_jwks=proposed_jwks, retire=retire,
    )
