"""Tenant access checks. Unknown tenant and no access both return 404 (no existence leak).

Access is per client: everyone, including Core8 platform admins, needs an explicit
tenant_members row. Platform admins may create tenants (and become owner of the ones they
create) but have no implicit access to other tenants' data. The one exception: platform
admins own the Core8 internal tenant (Core8's own workspace) implicitly.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException

from business_brain.repository import BrainRepository, get_membership_role, tenant_exists
from security.jwt_auth import require_jwt
from tenancy import INTERNAL_TENANT_ID

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
    if role is None and tenant_id == INTERNAL_TENANT_ID and user.get("role") == PLATFORM_ADMIN:
        role = "owner"
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


def query_tenant(min_role: str):
    """Like tenant_role, but the tenant comes from an optional ?tenant_id= query parameter and
    defaults to the Core8 internal tenant. Used by operational endpoints (conversations,
    Instagram, media) that predate multi-tenancy."""
    needed = ROLE_RANK[min_role]

    async def dep(tenant_id: str | None = None, user: dict = Depends(require_jwt)) -> TenantAccess:
        access = await resolve_access(tenant_id or INTERNAL_TENANT_ID, user)
        if access is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        if ROLE_RANK[access.role] < needed:
            raise HTTPException(status_code=403, detail=f"Requires tenant role '{min_role}'")
        return access

    return dep
