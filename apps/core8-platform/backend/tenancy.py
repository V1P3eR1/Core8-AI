"""Server-side tenant context for operational data (leads, events, posts, …).

The active tenant is set by the server — per WebSocket chat, request or scheduler job — and
read by tools and data functions. It is never taken from model/tool input, so an agent cannot
reach another tenant's rows by naming them.

Sessions that don't name a tenant run in the Core8 internal tenant, which holds all data
created before multi-tenancy (CORE8-005).
"""

from contextlib import contextmanager
from contextvars import ContextVar

INTERNAL_TENANT_ID = "core8-internal"
INTERNAL_TENANT_NAME = "Core8 (internal)"

_current: ContextVar[str | None] = ContextVar("core8_tenant_id", default=None)


class TenantContextError(RuntimeError):
    """Raised when tenant data is accessed with no tenant in context."""


def current_tenant() -> str:
    tid = _current.get()
    if not tid:
        raise TenantContextError("No tenant in context for a tenant-scoped operation")
    return tid


@contextmanager
def use_tenant(tenant_id: str):
    if not tenant_id:
        raise ValueError("tenant_id is required")
    token = _current.set(tenant_id)
    try:
        yield tenant_id
    finally:
        _current.reset(token)
