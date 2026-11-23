"""Offline tenant authorization policy fixture; no JWT decoding or DB access.

Caller must supply a *verified* identity and server-fetched memberships.
Never pass user-controlled membership lists in production.
"""

def resolve_tenant(*, identity, requested_tenant_id, memberships, required_permission="lead:intake"):
    if not isinstance(identity, dict) or identity.get("verified") is not True:
        return {"ok": False, "reason": "unauthenticated"}
    subject = identity.get("sub")
    if not isinstance(subject, str) or not subject:
        return {"ok": False, "reason": "unauthenticated"}
    if not isinstance(requested_tenant_id, str) or not requested_tenant_id:
        return {"ok": False, "reason": "invalid_tenant"}
    if not isinstance(memberships, list):
        return {"ok": False, "reason": "forbidden"}
    for membership in memberships:
        if not isinstance(membership, dict):
            continue
        if (membership.get("user_id") == subject
                and membership.get("tenant_id") == requested_tenant_id
                and membership.get("active") is True
                and isinstance(membership.get("permissions"), list)
                and required_permission in membership["permissions"]):
            return {"ok": True, "trusted_tenant_id": requested_tenant_id}
    return {"ok": False, "reason": "forbidden"}
