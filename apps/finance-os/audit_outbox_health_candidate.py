"""Read-only disposable audit outbox operational counters.

No HTTP endpoint. Caller requires separately authenticated and authorized
namespace scope; this helper DOES NOT authenticate its caller or send alerts.
"""
import re
from tenant_access import FinanceAccessDenied

_NS = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")


def audit_outbox_health(conn, *, namespace, max_attempts=5):
    if (type(namespace) is not str or not _NS.fullmatch(namespace)
            or type(max_attempts) is not int or
            not 1 <= max_attempts <= 20):
        raise FinanceAccessDenied("Finance audit export denied")
    row = conn.execute(
        """SELECT
             count(*) FILTER (WHERE o.delivered_at IS NULL),
             count(*) FILTER (WHERE o.delivered_at IS NOT NULL),
             count(*) FILTER (WHERE o.delivered_at IS NULL
               AND o.delivery_attempts >= %s),
             count(*) FILTER (WHERE o.delivered_at IS NULL
               AND o.delivery_attempts < %s
               AND o.lease_until > clock_timestamp()),
             count(*) FILTER (WHERE o.delivered_at IS NULL
               AND o.delivery_attempts < %s
               AND (o.lease_until IS NULL OR
                    o.lease_until <= clock_timestamp())
               AND (o.next_attempt_at IS NULL OR
                    o.next_attempt_at <= clock_timestamp()))
           FROM finance_key_audit_outbox_candidate o
           JOIN finance_key_approval_audit_candidate a ON a.id=o.audit_id
           JOIN finance_key_approval_candidate p ON p.approval_id=a.approval_id
          WHERE p.namespace=%s""",
        (max_attempts, max_attempts, max_attempts, namespace),
    ).fetchone()
    if row is None:
        raise FinanceAccessDenied("Finance audit export denied")
    return dict(zip(
        ("pending", "delivered", "exhausted", "leased", "ready"),
        map(int, row),
    ))
