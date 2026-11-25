"""Review-only server-side finance membership resolver (NOT an identity verifier).

An upstream trusted OIDC verifier must establish the immutable subject before
calling this function. Do not construct TrustedSubject from request headers,
unverified JWT payloads or user input. No HTTP routes use this module.
"""
from dataclasses import dataclass
from tenant_access import (
    FinanceAccessDenied, ROLE_ACTIONS, SUBJECT_RE, TENANT_RE,
    VerifiedFinancePrincipal,
)

@dataclass(frozen=True)
class TrustedSubject:
    """Contract for an upstream verified identity; not proof of authentication."""
    value: str


def resolve_finance_membership(conn, *, subject: TrustedSubject,
                               tenant_id: str) -> VerifiedFinancePrincipal:
    """Resolve one ACTIVE role from server-controlled membership rows.

    Fails closed on zero, multiple, malformed or disabled memberships.
    The SQL is tenant-scoped and parameterized; never trusts role claims.
    """
    if type(subject) is not TrustedSubject or not isinstance(subject.value, str):
        raise FinanceAccessDenied("Finance access denied")
    if SUBJECT_RE.fullmatch(subject.value) is None:
        raise FinanceAccessDenied("Finance access denied")
    if not isinstance(tenant_id, str) or TENANT_RE.fullmatch(tenant_id) is None:
        raise FinanceAccessDenied("Finance access denied")
    rows = conn.execute(
        """
        SELECT role, enabled
        FROM finance_membership_candidate
        WHERE subject_id = %s AND organization_id = %s
        """, (subject.value, tenant_id)
    ).fetchall()
    if len(rows) != 1:
        raise FinanceAccessDenied("Finance access denied")
    role, enabled = rows[0]
    if not isinstance(role, str) or role not in ROLE_ACTIONS or enabled is not True:
        raise FinanceAccessDenied("Finance access denied")
    return VerifiedFinancePrincipal(
        subject=subject.value, tenant_id=tenant_id, role=role, enabled=True
    )
