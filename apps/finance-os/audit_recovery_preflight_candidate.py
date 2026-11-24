"""Read-only floor-ahead recovery preflight; NEVER applies recovery.

A separately authenticated operator must source a proposed signed keyring
snapshot from independently retained incident evidence. This function cannot
prove the provenance, operator approval, or intent of the proposal: a valid
MAC is not proof of authorized key rotation. No database or floor updates.
"""
import hashlib
import json
from dataclasses import dataclass

from audit_floor_diagnostics_candidate import diagnose_audit_keyring
from audit_keyring_state_candidate import import_audit_keyring_state
from audit_keyring_store_candidate import _require_idle
from tenant_access import FinanceAccessDenied


@dataclass(frozen=True)
class RecoveryPreflight:
    namespace: str
    status: str
    floor_generation: int
    database_generation: int
    candidate_sha256: str
    operator_review_required: bool = True


def preview_floor_ahead_recovery(conn, *, floor, namespace, signing_key,
                                 trusted_key_material, proposed_snapshot):
    """Validate one-step floor-ahead candidate, without any repairs.

    Caller MUST independently authenticate proposed snapshot provenance and
    dual-operator approvals. A signature is necessary, not sufficient.
    A concurrent writer may invalidate the result immediately: a real repair
    must recheck everything under authorized transaction/lease controls.
    """
    _require_idle(conn)
    diagnosis = diagnose_audit_keyring(
        conn, floor=floor, namespace=namespace, signing_key=signing_key,
        trusted_key_material=trusted_key_material,
    )
    if (diagnosis.status != "floor_ahead" or
            diagnosis.database_generation is None or
            diagnosis.floor_generation != diagnosis.database_generation + 1 or
            type(proposed_snapshot) is not bytes):
        raise FinanceAccessDenied("Finance recovery preflight denied")
    # Independently verify signed current DB snapshot at its own generation,
    # despite floor being ahead; never grant it production signing authority.
    row = conn.execute(
        """SELECT signed_snapshot FROM finance_audit_keyring_store_candidate
           WHERE namespace=%s AND generation=%s""",
        (namespace, diagnosis.database_generation),
    ).fetchone()
    if row is None:
        raise FinanceAccessDenied("Finance recovery preflight denied")
    try:
        old = import_audit_keyring_state(
            bytes(row[0]), signing_key=signing_key,
            expected_generation=diagnosis.database_generation,
            trusted_key_material=_material_subset(row[0], trusted_key_material),
        )
        new = import_audit_keyring_state(
            proposed_snapshot, signing_key=signing_key,
            expected_generation=diagnosis.floor_generation,
            trusted_key_material=_material_subset(proposed_snapshot,
                                                  trusted_key_material),
        )
        with old._lock, new._lock:
            dropped = set(old._keys) - set(new._keys)
            if (not old._retired.issubset(new._retired)
                    or dropped != new._retired - old._retired
                    or any(k in old._keys and old._keys[k] != value
                           for k, value in new._keys.items())):
                raise ValueError("non-monotonic key transition")
        # Another observation can race with us; only report a preview.
        if floor.read(namespace) != diagnosis.floor_generation:
            raise ValueError("floor changed during preview")
    except Exception:
        raise FinanceAccessDenied("Finance recovery preflight denied") from None
    return RecoveryPreflight(
        namespace=namespace, status="review_required",
        floor_generation=diagnosis.floor_generation,
        database_generation=diagnosis.database_generation,
        candidate_sha256=hashlib.sha256(proposed_snapshot).hexdigest(),
    )


def _material_subset(blob, trusted_key_material):
    """Select a signed inventory subset; MAC checked separately by importer."""
    if type(trusted_key_material) is not dict:
        raise FinanceAccessDenied("Finance recovery preflight denied")
    try:
        state = json.loads(bytes(blob))["state"]
        kids = [v["kid"] for v in state["keys"]]
        if len(set(kids)) != len(kids):
            raise ValueError("duplicated key IDs")
        return {kid: trusted_key_material[kid] for kid in kids}
    except Exception:
        raise FinanceAccessDenied("Finance recovery preflight denied") from None
