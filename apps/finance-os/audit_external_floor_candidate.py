"""Unwired audit-signing keyring coordinator with independent floor contract.

External floor must be a separately administered, authenticated durable
linearizable CAS service. This candidate implements NONE of that infrastructure.
Mock floors in tests are not production authority. No live endpoints, secrets,
production database migrations or network calls.
"""
from audit_keyring_store_candidate import (
    advance_audit_keyring_store, recover_audit_keyring_store,
)
from audit_keyring_state_candidate import (
    export_audit_keyring_state, import_audit_keyring_state,
)
from audit_key_rotation_candidate import AuditKeyringCandidate
from external_floor_candidate import IndependentGenerationFloor
from tenant_access import FinanceAccessDenied


def _floor_read(floor, namespace):
    if not isinstance(floor, IndependentGenerationFloor):
        raise FinanceAccessDenied("Finance audit floor denied")
    try:
        value = floor.read(namespace)
        if type(value) is not int or value < 1:
            raise ValueError("invalid floor value")
        return value
    except Exception:
        raise FinanceAccessDenied("Finance audit floor denied") from None


def recover_audit_with_floor(conn, *, namespace, floor, signing_key,
                             trusted_key_material):
    """Fail closed if database state trails or differs from trusted floor."""
    version = _floor_read(floor, namespace)
    return recover_audit_keyring_store(
        conn, namespace=namespace, signing_key=signing_key,
        external_generation=version,
        trusted_key_material=trusted_key_material,
    )


def rotate_audit_with_floor(conn, *, namespace, floor, signing_key,
                            trusted_key_material, expected_generation,
                            new_registry):
    """Preflight transition before external CAS; update database afterward.

    If the external floor advances and the DB write fails, the DB is
    deliberately inaccessible for key recovery until an independently
    approved, auditable recovery fixes the state WITHOUT lowering the floor.
    """
    if (type(expected_generation) is not int or expected_generation < 1
            or type(new_registry) is not AuditKeyringCandidate
            or new_registry.generation != expected_generation + 1):
        raise FinanceAccessDenied("Finance audit floor denied")
    current = _floor_read(floor, namespace)
    if current != expected_generation:
        raise FinanceAccessDenied("Finance audit floor denied")
    # Verify live signed DB state against current independent floor.
    prior = recover_audit_keyring_store(
        conn, namespace=namespace, signing_key=signing_key,
        external_generation=current,
        trusted_key_material=trusted_key_material,
    )
    # Validate prospective signed state, identity and monotonic tombstones
    # WITHOUT advancing the floor if this proposal is invalid.
    proposed_blob = export_audit_keyring_state(
        new_registry, signing_key=signing_key,
    )
    prospective = import_audit_keyring_state(
        proposed_blob, signing_key=signing_key,
        expected_generation=current + 1,
        trusted_key_material={
            key_id: trusted_key_material[key_id]
            for key_id in new_registry._keys
        },
    )
    with prior._lock, prospective._lock:
        if (not prior._retired.issubset(prospective._retired)
                or set(prior._keys) - set(prospective._keys)
                != prospective._retired - prior._retired
                or any(k in prior._keys and prior._keys[k] != value
                       for k, value in prospective._keys.items())):
            raise FinanceAccessDenied("Finance audit floor denied")
    try:
        advanced = floor.compare_and_advance(
            namespace, current, current + 1,
        )
    except Exception:
        raise FinanceAccessDenied("Finance audit floor denied") from None
    if advanced is not True:
        raise FinanceAccessDenied("Finance audit floor denied")
    return advance_audit_keyring_store(
        conn, namespace=namespace, signing_key=signing_key,
        expected_generation=current, external_generation=current + 1,
        new_registry=new_registry,
        trusted_key_material=trusted_key_material,
    )
