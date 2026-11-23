"""Unwired PostgreSQL transaction/CAS adapter for authenticated JWKS snapshots.

REVIEW ONLY: caller must be an independently authorized operator with a
trusted signing key and a separately durable, authoritative generation floor.
This database cannot protect against whole-database snapshot rollback.
No schema changes, connections, I/O, secrets, or API routes are created here.
"""
import re

from jwks_state_candidate import export_registry_state, import_registry_state
from pinned_jwks_candidate import PinnedJwksRegistry
from tenant_access import FinanceAccessDenied

_NAMESPACE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")


def _inputs(namespace, minimum_generation, signing_key):
    if (type(namespace) is not str or not _NAMESPACE.fullmatch(namespace) or
            type(minimum_generation) is not int or minimum_generation < 1 or
            type(signing_key) is not bytes or len(signing_key) < 32):
        raise FinanceAccessDenied("Finance key configuration denied")


def initialize_jwks_store(conn, *, namespace, jwks, signing_key):
    """One-time bootstrap by trusted test admin; never overwrite existing row."""
    _inputs(namespace, 1, signing_key)
    registry = PinnedJwksRegistry(jwks, generation=1)
    blob = export_registry_state(registry, signing_key=signing_key)
    with conn.transaction():
        result = conn.execute(
            """INSERT INTO finance_jwks_store_candidate
                 (namespace, generation, signed_snapshot)
               VALUES (%s, %s, %s)
               ON CONFLICT (namespace) DO NOTHING
               RETURNING generation""",
            (namespace, 1, blob),
        ).fetchone()
        if result is None:
            raise FinanceAccessDenied("Finance key configuration denied")
    return 1


def recover_jwks_store(conn, *, namespace, signing_key, minimum_generation):
    """Read authenticated snapshot; floor comes from independent trusted store."""
    _inputs(namespace, minimum_generation, signing_key)
    row = conn.execute(
        """SELECT generation, signed_snapshot
           FROM finance_jwks_store_candidate WHERE namespace=%s""",
        (namespace,),
    ).fetchone()
    if row is None:
        raise FinanceAccessDenied("Finance key configuration denied")
    generation, blob = row
    registry = import_registry_state(
        bytes(blob), signing_key=signing_key, minimum_generation=minimum_generation
    )
    if registry.snapshot()[0] != generation:
        raise FinanceAccessDenied("Finance key configuration denied")
    return registry


def rotate_jwks_store(conn, *, namespace, signing_key, minimum_generation,
                      expected_generation, proposed_jwks, retire=()):
    """Serialize one approved rotation and persist keys + tombstones atomically.

    A row lock prevents concurrent changes. A compare-and-swap on the
    expected generation rejects a stale operator/client retry. This is not
    a real operator authorization flow or a durable anti-rollback floor.
    """
    _inputs(namespace, minimum_generation, signing_key)
    if type(expected_generation) is not int or expected_generation < 1:
        raise FinanceAccessDenied("Finance key configuration denied")
    with conn.transaction():
        row = conn.execute(
            """SELECT generation, signed_snapshot
               FROM finance_jwks_store_candidate
               WHERE namespace=%s FOR UPDATE""",
            (namespace,),
        ).fetchone()
        if row is None or row[0] != expected_generation:
            raise FinanceAccessDenied("Finance key configuration denied")
        registry = import_registry_state(
            bytes(row[1]), signing_key=signing_key,
            minimum_generation=minimum_generation,
        )
        if registry.snapshot()[0] != expected_generation:
            raise FinanceAccessDenied("Finance key configuration denied")
        next_generation = expected_generation + 1
        registry.replace(proposed_jwks, generation=next_generation, retire=retire)
        signed = export_registry_state(registry, signing_key=signing_key)
        changed = conn.execute(
            """UPDATE finance_jwks_store_candidate
                  SET generation=%s, signed_snapshot=%s, updated_at=now()
                WHERE namespace=%s AND generation=%s
                RETURNING generation""",
            (next_generation, signed, namespace, expected_generation),
        ).fetchone()
        if changed is None:
            raise FinanceAccessDenied("Finance key configuration denied")
    return next_generation
