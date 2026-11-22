"""Review-only finance authorization policy, independent of HTTP/JWT parsing.

Security boundary: caller MUST provide a principal from a separately verified
identity provider plus a server-side verified tenant membership. Neither the
request body, headers, Stripe metadata nor a decoded-but-unverified JWT is proof
of membership. This helper does not enable any finance endpoint.
"""
from dataclasses import dataclass
from typing import FrozenSet
import re

TENANT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")
SUBJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_:.@|-]{2,199}$")
ACTIONS = frozenset({"finance:read", "finance:review", "finance:operate"})
ROLE_ACTIONS = {
    "viewer": frozenset({"finance:read"}),
    "analyst": frozenset({"finance:read", "finance:review"}),
    "operator": frozenset({"finance:read", "finance:review", "finance:operate"}),
}


class FinanceAccessDenied(PermissionError):
    """Authorization denied; don't reveal whether the requested tenant exists."""


@dataclass(frozen=True)
class VerifiedFinancePrincipal:
    subject: str
    tenant_id: str
    role: str
    enabled: bool = True


def require_finance_permission(principal: VerifiedFinancePrincipal, *,
                               tenant_id: str, action: str) -> None:
    """Permit only validated, exact tenant membership and a role's explicit action.

    A valid-looking principal is not self-authenticating. The integration must
    construct this object only after validating tokens and memberships server-side.
    """
    if type(principal) is not VerifiedFinancePrincipal:
        raise FinanceAccessDenied("Finance access denied")
    if not (isinstance(principal.subject, str)
            and SUBJECT_RE.fullmatch(principal.subject)):
        raise FinanceAccessDenied("Finance access denied")
    if not (isinstance(tenant_id, str) and TENANT_RE.fullmatch(tenant_id)):
        raise FinanceAccessDenied("Finance access denied")
    if not (isinstance(principal.tenant_id, str)
            and TENANT_RE.fullmatch(principal.tenant_id)):
        raise FinanceAccessDenied("Finance access denied")
    if type(principal.enabled) is not bool or not principal.enabled:
        raise FinanceAccessDenied("Finance access denied")
    if action not in ACTIONS or action not in ROLE_ACTIONS.get(principal.role, ()):
        raise FinanceAccessDenied("Finance access denied")
    if principal.tenant_id != tenant_id:
        raise FinanceAccessDenied("Finance access denied")
