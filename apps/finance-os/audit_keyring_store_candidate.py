"""Review-only transactional PostgreSQL store for signed audit key metadata.

Strictly disposable CI use. No key bytes in DB, no actual KMS, authorization,
independent generation-floor CAS, production migration, or live endpoint.
A caller must obtain an independently trusted external generation and key map.
"""
import json
import re

from audit_keyring_state_candidate import (
    export_audit_keyring_state, import_audit_keyring_state,
)
from audit_key_rotation_candidate import AuditKeyringCandidate
from tenant_access import FinanceAccessDenied

_NS = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")


def _validate_namespace(namespace):
    if type(namespace) is not str or not _NS.fullmatch(namespace):
        raise FinanceAccessDenied("Finance audit metadata store denied")


def _require_idle(conn):
    from psycopg.pq import TransactionStatus
    if (conn.autocommit is not True or
            conn.info.transaction_status != TransactionStatus.IDLE):
        raise FinanceAccessDenied("Finance audit metadata store denied")


def _key_subset(blob, trusted_key_material):
    # The authenticated importer verifies the exact inventory. This parser
    # only chooses the subset to pass to it, never authenticates metadata.
    try:
        state = json.loads(blob)["state"]
        ids = [v["kid"] for v in state["keys"]]
        if (type(trusted_key_material) is not dict or
                len(set(ids)) != len(ids) or
                not all(type(k) is str and k in trusted_key_material for k in ids)):
            raise ValueError("missing key")
        return {k: trusted_key_material[k] for k in ids}
    except Exception:
        raise FinanceAccessDenied("Finance audit metadata store denied") from None


def initialize_audit_keyring_store(conn, *, namespace, registry, signing_key):
    """Trusted CI administrator bootstraps once, never overwriting a row."""
    _validate_namespace(namespace)
    _require_idle(conn)
    if type(registry) is not AuditKeyringCandidate or registry.generation != 1:
        raise FinanceAccessDenied("Finance audit metadata store denied")
    snapshot = export_audit_keyring_state(registry, signing_key=signing_key)
    with conn.transaction():
        row = conn.execute(
            """INSERT INTO finance_audit_keyring_store_candidate
                 (namespace, generation, signed_snapshot)
               VALUES (%s, 1, %s) ON CONFLICT (namespace) DO NOTHING
               RETURNING generation""",
            (namespace, snapshot),
        ).fetchone()
        if row is None:
            raise FinanceAccessDenied("Finance audit metadata store denied")
    return 1


def recover_audit_keyring_store(conn, *, namespace, signing_key,
                                external_generation, trusted_key_material):
    """Do not recover from an old DB row when the independent floor advanced."""
    _validate_namespace(namespace)
    if type(external_generation) is not int or external_generation < 1:
        raise FinanceAccessDenied("Finance audit metadata store denied")
    row = conn.execute(
        """SELECT generation, signed_snapshot
           FROM finance_audit_keyring_store_candidate WHERE namespace=%s""",
        (namespace,),
    ).fetchone()
    if row is None or type(row[0]) is not int or row[0] != external_generation:
        raise FinanceAccessDenied("Finance audit metadata store denied")
    blob = bytes(row[1])
    return import_audit_keyring_state(
        blob, signing_key=signing_key,
        expected_generation=external_generation,
        trusted_key_material=_key_subset(blob, trusted_key_material),
    )


def advance_audit_keyring_store(conn, *, namespace, signing_key,
                                external_generation, expected_generation,
                                new_registry, trusted_key_material):
    """Persist a strictly monotonic keyring transition with PostgreSQL CAS.

    The *real* independent floor must be advanced BEFORE invoking this method,
    so external_generation MUST equal expected_generation+1. The previous
    signed state is verified against previous generation under a row lock.
    This function does not itself advance or validate the trusted floor
    service: it consumes an independently supplied value. If the DB update
    fails after floor CAS, fail closed until manual audited recovery.
    """
    _validate_namespace(namespace)
    _require_idle(conn)
    if (type(expected_generation) is not int or expected_generation < 1
            or type(external_generation) is not int
            or external_generation != expected_generation + 1
            or type(new_registry) is not AuditKeyringCandidate
            or new_registry.generation != external_generation):
        raise FinanceAccessDenied("Finance audit metadata store denied")
    proposed = export_audit_keyring_state(
        new_registry, signing_key=signing_key
    )
    with conn.transaction():
        row = conn.execute(
            """SELECT generation, signed_snapshot
               FROM finance_audit_keyring_store_candidate
               WHERE namespace=%s FOR UPDATE""",
            (namespace,),
        ).fetchone()
        if row is None or row[0] != expected_generation:
            raise FinanceAccessDenied("Finance audit metadata store denied")
        old_blob = bytes(row[1])
        prior = import_audit_keyring_state(
            old_blob, signing_key=signing_key,
            expected_generation=expected_generation,
            trusted_key_material=_key_subset(old_blob, trusted_key_material),
        )
        next_ring = import_audit_keyring_state(
            proposed, signing_key=signing_key,
            expected_generation=external_generation,
            trusted_key_material=_key_subset(proposed, trusted_key_material),
        )
        # Verify continuous history, revocation and unchanged old key bytes.
        with prior._lock, next_ring._lock:
            if (not prior._retired.issubset(next_ring._retired)
                    or set(prior._keys) - set(next_ring._keys)
                    != next_ring._retired - prior._retired
                    or any(k in prior._keys and prior._keys[k] != value
                           for k, value in next_ring._keys.items())):
                raise FinanceAccessDenied("Finance audit metadata store denied")
        result = conn.execute(
            """UPDATE finance_audit_keyring_store_candidate
                  SET generation=%s, signed_snapshot=%s,
                      updated_at=clock_timestamp()
                WHERE namespace=%s AND generation=%s
                RETURNING generation""",
            (external_generation, proposed, namespace, expected_generation),
        ).fetchone()
        if result is None:
            raise FinanceAccessDenied("Finance audit metadata store denied")
    return external_generation
