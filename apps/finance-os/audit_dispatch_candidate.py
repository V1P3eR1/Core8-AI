"""Offline, review-only audit outbox dispatcher candidate.

Sink is supplied by trusted tests. NO HTTP client, network, secrets, producer
integration or background scheduler exists here. This is at-least-once delivery:
a sink can accept an event before local acknowledgment fails, so every external
receiver MUST durably deduplicate by stable event_id.

Do not enable in production without an independently authenticated sink,
least-privileged DB roles, durable retention, crash recovery and monitoring.
"""
from dataclasses import dataclass
import re
from uuid import uuid4

from tenant_access import FinanceAccessDenied

_NAMESPACE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")

@dataclass(frozen=True)
class ClaimedAuditEvent:
    audit_id: int
    event_id: str
    payload: dict
    lease_token: str
    attempts: int


def _require_idle(conn):
    # Import only upon execution; lightweight unit-only CI lacks psycopg.
    from psycopg.pq import TransactionStatus
    if (conn.autocommit is not True or
            conn.info.transaction_status != TransactionStatus.IDLE):
        raise FinanceAccessDenied("Finance audit export denied")


def claim_next(conn, *, namespace, lease_seconds=30, max_attempts=5):
    """Claim one event with short transaction and SKIP LOCKED row lock."""
    if (type(namespace) is not str or not _NAMESPACE.fullmatch(namespace) or
            type(lease_seconds) is not int or not 1 <= lease_seconds <= 300 or
            type(max_attempts) is not int or not 1 <= max_attempts <= 20):
        raise FinanceAccessDenied("Finance audit export denied")
    _require_idle(conn)
    token = uuid4().hex
    with conn.transaction():
        row = conn.execute(
            """SELECT o.audit_id, o.event_id, o.payload, o.delivery_attempts
                 FROM finance_key_audit_outbox_candidate o
                 JOIN finance_key_approval_audit_candidate a ON a.id=o.audit_id
                 JOIN finance_key_approval_candidate p ON p.approval_id=a.approval_id
                WHERE p.namespace=%s AND o.delivered_at IS NULL
                  AND o.delivery_attempts < %s
                  AND (o.lease_until IS NULL OR o.lease_until < clock_timestamp())
                  AND (o.next_attempt_at IS NULL
                       OR o.next_attempt_at <= clock_timestamp())
                ORDER BY o.audit_id
                FOR UPDATE OF o SKIP LOCKED LIMIT 1""",
            (namespace, max_attempts),
        ).fetchone()
        if row is None:
            return None
        audit_id, event_id, payload, count = row
        conn.execute(
            """UPDATE finance_key_audit_outbox_candidate
                  SET lease_token=%s,
                      lease_until=clock_timestamp() + (%s * interval '1 second'),
                      delivery_attempts=delivery_attempts+1
                WHERE audit_id=%s""",
            (token, lease_seconds, audit_id),
        )
    return ClaimedAuditEvent(audit_id, event_id, payload, token, count + 1)


def ack_claim(conn, claim):
    """Only the holder of the current, unexpired lease can mark delivery."""
    if type(claim) is not ClaimedAuditEvent:
        raise FinanceAccessDenied("Finance audit export denied")
    _require_idle(conn)
    with conn.transaction():
        row = conn.execute(
            """UPDATE finance_key_audit_outbox_candidate
                  SET delivered_at=clock_timestamp(),
                      lease_token=NULL, lease_until=NULL, next_attempt_at=NULL
                WHERE audit_id=%s AND event_id=%s
                  AND lease_token=%s AND lease_until > clock_timestamp()
                  AND delivered_at IS NULL
                RETURNING audit_id""",
            (claim.audit_id, claim.event_id, claim.lease_token),
        ).fetchone()
    return row is not None


def retry_claim(conn, claim, *, backoff_seconds=30):
    """Release a claim after an in-process sink failure with bounded retry."""
    if (type(claim) is not ClaimedAuditEvent or
            type(backoff_seconds) is not int or
            not 1 <= backoff_seconds <= 3600):
        raise FinanceAccessDenied("Finance audit export denied")
    _require_idle(conn)
    with conn.transaction():
        row = conn.execute(
            """UPDATE finance_key_audit_outbox_candidate
                  SET lease_token=NULL, lease_until=NULL,
                      next_attempt_at=clock_timestamp() + (%s * interval '1 second')
                WHERE audit_id=%s AND event_id=%s
                  AND lease_token=%s AND lease_until > clock_timestamp()
                  AND delivered_at IS NULL
                RETURNING audit_id""",
            (backoff_seconds, claim.audit_id, claim.event_id, claim.lease_token),
        ).fetchone()
    return row is not None


def dispatch_one(conn, *, namespace, sink, lease_seconds=30, backoff_seconds=30):
    """Run ONE explicit, synchronous CI dispatch; never automatic or remote.

    sink.accept(event_id, payload) MUST return True only after durable receiver
    acknowledgment. A lost response may cause redelivery; the receiver must
    deduplicate. Neither false nor exceptions mark the event delivered.
    """
    if sink is None or not callable(getattr(sink, "accept", None)):
        raise FinanceAccessDenied("Finance audit export denied")
    claim = claim_next(conn, namespace=namespace, lease_seconds=lease_seconds)
    if claim is None:
        return "idle"
    try:
        accepted = sink.accept(claim.event_id, dict(claim.payload))
    except Exception:
        accepted = False
    if accepted is True:
        return "delivered" if ack_claim(conn, claim) else "uncertain"
    retry_claim(conn, claim, backoff_seconds=backoff_seconds)
    return "retry"
)


@dataclass(frozen=True)
class ClaimedAuditEvent:
    audit_id: int
    event_id: str
    payload: dict
    lease_token: str
    attempts: int


def _require_idle(conn):
    # Import only upon execution; lightweight unit-only CI lacks psycopg.
    from psycopg.pq import TransactionStatus
    if (conn.autocommit is not True or
            conn.info.transaction_status != TransactionStatus.IDLE):
        raise FinanceAccessDenied("Finance audit export denied")


def claim_next(conn, *, lease_seconds=30, max_attempts=5):
    """Claim one event with short transaction and SKIP LOCKED row lock."""
    if (type(lease_seconds) is not int or not 1 <= lease_seconds <= 300 or
            type(max_attempts) is not int or not 1 <= max_attempts <= 20):
        raise FinanceAccessDenied("Finance audit export denied")
    _require_idle(conn)
    token = uuid4().hex
    with conn.transaction():
        row = conn.execute(
            """SELECT audit_id, event_id, payload, delivery_attempts
                 FROM finance_key_audit_outbox_candidate
                WHERE delivered_at IS NULL
                  AND delivery_attempts < %s
                  AND (lease_until IS NULL OR lease_until < clock_timestamp())
                  AND (next_attempt_at IS NULL
                       OR next_attempt_at <= clock_timestamp())
                ORDER BY audit_id
                FOR UPDATE SKIP LOCKED LIMIT 1""",
            (max_attempts,),
        ).fetchone()
        if row is None:
            return None
        audit_id, event_id, payload, count = row
        conn.execute(
            """UPDATE finance_key_audit_outbox_candidate
                  SET lease_token=%s,
                      lease_until=clock_timestamp() + (%s * interval '1 second'),
                      delivery_attempts=delivery_attempts+1
                WHERE audit_id=%s""",
            (token, lease_seconds, audit_id),
        )
    return ClaimedAuditEvent(audit_id, event_id, payload, token, count + 1)


def ack_claim(conn, claim):
    """Only the holder of the current, unexpired lease can mark delivery."""
    if type(claim) is not ClaimedAuditEvent:
        raise FinanceAccessDenied("Finance audit export denied")
    _require_idle(conn)
    with conn.transaction():
        row = conn.execute(
            """UPDATE finance_key_audit_outbox_candidate
                  SET delivered_at=clock_timestamp(),
                      lease_token=NULL, lease_until=NULL, next_attempt_at=NULL
                WHERE audit_id=%s AND event_id=%s
                  AND lease_token=%s AND lease_until > clock_timestamp()
                  AND delivered_at IS NULL
                RETURNING audit_id""",
            (claim.audit_id, claim.event_id, claim.lease_token),
        ).fetchone()
    return row is not None


def retry_claim(conn, claim, *, backoff_seconds=30):
    """Release a claim after an in-process sink failure with bounded retry."""
    if (type(claim) is not ClaimedAuditEvent or
            type(backoff_seconds) is not int or
            not 1 <= backoff_seconds <= 3600):
        raise FinanceAccessDenied("Finance audit export denied")
    _require_idle(conn)
    with conn.transaction():
        row = conn.execute(
            """UPDATE finance_key_audit_outbox_candidate
                  SET lease_token=NULL, lease_until=NULL,
                      next_attempt_at=clock_timestamp() + (%s * interval '1 second')
                WHERE audit_id=%s AND event_id=%s
                  AND lease_token=%s AND lease_until > clock_timestamp()
                  AND delivered_at IS NULL
                RETURNING audit_id""",
            (backoff_seconds, claim.audit_id, claim.event_id, claim.lease_token),
        ).fetchone()
    return row is not None


def dispatch_one(conn, *, sink, lease_seconds=30, backoff_seconds=30):
    """Run ONE explicit, synchronous CI dispatch; never automatic or remote.

    sink.accept(event_id, payload) MUST return True only after durable receiver
    acknowledgment. A lost response may cause redelivery; the receiver must
    deduplicate. Neither false nor exceptions mark the event delivered.
    """
    if sink is None or not callable(getattr(sink, "accept", None)):
        raise FinanceAccessDenied("Finance audit export denied")
    claim = claim_next(conn, lease_seconds=lease_seconds)
    if claim is None:
        return "idle"
    try:
        accepted = sink.accept(claim.event_id, dict(claim.payload))
    except Exception:
        accepted = False
    if accepted is True:
        return "delivered" if ack_claim(conn, claim) else "uncertain"
    retry_claim(conn, claim, backoff_seconds=backoff_seconds)
    return "retry"
