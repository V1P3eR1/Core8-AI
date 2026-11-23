"""Offline, read-only audit keyring recovery diagnostics for a trusted operator.

Sandbox-only; never repairs the trusted generation floor, DB row or keys.
Caller MUST be independently authenticated and authorized. No HTTP routes.
"""
from dataclasses import dataclass
import re

from audit_keyring_store_candidate import recover_audit_keyring_store
from external_floor_candidate import IndependentGenerationFloor
from tenant_access import FinanceAccessDenied

_NS = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")


@dataclass(frozen=True)
class AuditFloorDiagnosis:
    namespace: str
    status: str
    floor_generation: int
    database_generation: int | None


def diagnose_audit_keyring(conn, *, floor, namespace, signing_key,
                           trusted_key_material):
    """Fail closed for unreadable floor; report DB mismatch without mutation.

    Statuses: healthy, floor_ahead, database_ahead, snapshot_invalid,
    missing_database_state. No secrets or snapshot bytes are returned.
    Only a human-approved incident workflow may resolve discrepancies.
    """
    if (not isinstance(floor, IndependentGenerationFloor)
            or type(namespace) is not str or not _NS.fullmatch(namespace)):
        raise FinanceAccessDenied("Finance audit diagnostic denied")
    try:
        generation = floor.read(namespace)
        if type(generation) is not int or generation < 1:
            raise ValueError("invalid floor")
    except Exception:
        raise FinanceAccessDenied("Finance audit diagnostic denied") from None
    row = conn.execute(
        "SELECT generation FROM finance_audit_keyring_store_candidate WHERE namespace=%s",
        (namespace,),
    ).fetchone()
    if row is None:
        return AuditFloorDiagnosis(namespace, "missing_database_state",
                                   generation, None)
    db_generation = row[0]
    if type(db_generation) is not int or db_generation < 1:
        raise FinanceAccessDenied("Finance audit diagnostic denied")
    if generation != db_generation:
        status = "floor_ahead" if generation > db_generation else "database_ahead"
        return AuditFloorDiagnosis(namespace, status, generation, db_generation)
    try:
        recover_audit_keyring_store(
            conn, namespace=namespace, signing_key=signing_key,
            external_generation=generation,
            trusted_key_material=trusted_key_material,
        )
    except Exception:
        return AuditFloorDiagnosis(namespace, "snapshot_invalid",
                                   generation, db_generation)
    return AuditFloorDiagnosis(namespace, "healthy", generation, db_generation)
