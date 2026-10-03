"""Tenant access checks. Unknown tenant and no access both return 404 (no existence leak).

Access is per client: everyone, including Core8 platform admins, needs an explicit
tenant_members row. Platform admins may create tenants (and become owner of the ones they
create) but have no implicit access to other tenants' data.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException

from business_brain.repository import BrainRepository, get_membership_role, tenant_exists
from security.jwt_auth import require_jwt

ROLE_RANK = {"viewer": 1, "editor": 2, "owner": 3}
PLATFORM_ADMIN = "admin"


@dataclass
class TenantAccess:
    tenant_id: str
    user_id: str
    role: str          # 'owner' | 'editor' | 'viewer'
    repo: BrainRepository


async def resolve_access(tenant_id: str, user: dict) -> TenantAccess | None:
    if not await tenant_exists(tenant_id):
        return None
    role = await get_membership_role(tenant_id, user["sub"])
    if role is None:
        return None
    return TenantAccess(tenant_id, user["sub"], role, BrainRepository(tenant_id))


def tenant_role(min_role: str):
    """FastAPI dependency factory: JWT user with at least `min_role` on the path's tenant."""
    needed = ROLE_RANK[min_role]

    async def dep(tenant_id: str, user: dict = Depends(require_jwt)) -> TenantAccess:
        access = await resolve_access(tenant_id, user)
        if access is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        if ROLE_RANK[access.role] < needed:
            raise HTTPException(status_code=403, detail=f"Requires tenant role '{min_role}'")
        return access

    return dep
