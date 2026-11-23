"""Read-only, tenant-scoped Finance OS queries (not wired to HTTP).

Only a trusted identity adapter may construct the principal after token
verification and server-side membership lookup. This module does not verify
identity or establish a new API. Operational counts are NOT financial balances.
"""
from tenant_access import require_finance_permission


def read_inbox_status_counts(conn, *, principal, tenant_id):
    """Read aggregate status counts for exactly one authorized tenant.

    conn is a trusted, already-open DB connection. The SQL tenant condition is
    mandatory even though the caller has passed the policy check. Caller must
    use a read-only least-privilege database role in an actual service.
    """
    require_finance_permission(principal, tenant_id=tenant_id, action="finance:read")
    rows = conn.execute(
        """
        SELECT status, count(*) AS event_count
          FROM finance_stripe_event_inbox
         WHERE organization_id = %s
         GROUP BY status
         ORDER BY status
        """,
        (tenant_id,),
    ).fetchall()
    return {status: count for status, count in rows}
