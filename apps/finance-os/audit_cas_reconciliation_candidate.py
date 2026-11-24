"""Read-only response-loss reconciliation for audit generation CAS.

This DOES NOT retry the CAS, lower a floor, complete a PostgreSQL mutation,
or attribute a remote update to our lost request. An observed advanced floor
could equally have been advanced by another writer. The caller must use an
independently authenticated floor and an authorized incident workflow.
"""
from dataclasses import dataclass

from external_floor_candidate import IndependentGenerationFloor
from tenant_access import FinanceAccessDenied


@dataclass(frozen=True)
class LostAckReconciliation:
    status: str
    expected_generation: int
    requested_generation: int
    observed_generation: int | None


def reconcile_lost_cas_ack(*, floor, namespace, expected_generation,
                           requested_generation):
    """Inspect floor once after a lost CAS response; no write or retry.

    statuses:
      unchanged: floor still at expected; original update NOT confirmed
      advanced_or_later: floor is >= requested; original actor NOT identifiable
      unavailable: trusted floor read failed, must halt/ask operator

    Values lower than expected imply possible floor rollback: fail closed.
    """
    if (not isinstance(floor, IndependentGenerationFloor) or
            type(namespace) is not str or
            type(expected_generation) is not int or
            type(requested_generation) is not int or
            expected_generation < 1 or
            requested_generation != expected_generation + 1 or
            requested_generation > 2**63 - 1):
        raise FinanceAccessDenied("Finance CAS reconciliation denied")
    from re import fullmatch
    if fullmatch(r"[a-z][a-z0-9_-]{2,63}", namespace) is None:
        raise FinanceAccessDenied("Finance CAS reconciliation denied")
    try:
        observed = floor.read(namespace)
    except Exception:
        return LostAckReconciliation(
            "unavailable", expected_generation, requested_generation, None
        )
    if (type(observed) is not int or observed < expected_generation or
            observed > 2**63 - 1):
        raise FinanceAccessDenied("Finance CAS reconciliation denied")
    status = ("unchanged" if observed == expected_generation
              else "advanced_or_later")
    return LostAckReconciliation(
        status, expected_generation, requested_generation, observed
    )
