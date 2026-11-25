"""Disposable PostgreSQL approval ledger with atomic one-time consumption.

Unwired review candidate: the database connection and approval provisioning
must belong to a separately authenticated/authorized administrative service.
A fabricated StoredKeyApproval is not proof of human approval or identity.
Never expose this ledger via a request handler or grant API users SQL writes.
"""
import re

from key_approval_candidate import IndependentApprovalLedger, StoredKeyApproval
from tenant_access import FinanceAccessDenied

_ID = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
_NS = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_SUB = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_:.@|-]{2,199}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _validate(approval):
    if (type(approval) is not StoredKeyApproval
            or type(approval.approval_id) is not str
            or not _ID.fullmatch(approval.approval_id)
            or type(approval.requester_subject) is not str
            or not _SUB.fullmatch(approval.requester_subject)
            or type(approval.approver_subject) is not str
            or not _SUB.fullmatch(approval.approver_subject)
            or approval.requester_subject == approval.approver_subject
            or type(approval.proposal_sha256) is not str
            or not _SHA.fullmatch(approval.proposal_sha256)
            or type(approval.expires_at) is not int):
        raise FinanceAccessDenied("Finance key approval denied")


def provision_test_approval(conn, *, namespace, approval):
    """Trusted CI admin only; inserts immutable approval metadata once."""
    _validate(approval)
    if type(namespace) is not str or not _NS.fullmatch(namespace):
        raise FinanceAccessDenied("Finance key approval denied")
    with conn.transaction():
        row = conn.execute(
            """INSERT INTO finance_key_approval_candidate
                  (approval_id, namespace, requester_subject,
                   approver_subject, proposal_sha256, expires_at)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT (approval_id) DO NOTHING
               RETURNING approval_id""",
            (approval.approval_id, namespace,
             approval.requester_subject, approval.approver_subject,
             approval.proposal_sha256, approval.expires_at),
        ).fetchone()
        if row is None:
            raise FinanceAccessDenied("Finance key approval denied")


class PostgresApprovalCandidate(IndependentApprovalLedger):
    """Consume once using a conditional SQL update + same-transaction audit insert.

    Expiry uses PostgreSQL server clock, never request-provided time.
    Only dedicated autocommit, IDLE connections are accepted. This avoids
    returning success inside a caller-controlled transaction that can roll
    back after an external watermark is advanced. The cross-service commit
    gap still exists and requires explicit audited recovery.
    """

    def __init__(self, conn, *, namespace):
        if type(namespace) is not str or not _NS.fullmatch(namespace):
            raise FinanceAccessDenied("Finance key approval denied")
        self.conn = conn
        self.namespace = namespace

    def consume(self, approval_id, expected):
        _validate(expected)
        if type(approval_id) is not str or approval_id != expected.approval_id:
            return False
        # Disallow deferred commits and savepoints. Successful consumption
        # must have committed before the caller can invoke external key CAS.
        # A transaction begun by any caller (including autocommit=True with an
        # outer transaction context) is not safe for this integration boundary.
        from psycopg.pq import TransactionStatus
        if (self.conn.autocommit is not True or
                self.conn.info.transaction_status != TransactionStatus.IDLE):
            raise FinanceAccessDenied("Finance key approval denied")
        with self.conn.transaction():
            row = self.conn.execute(
                """UPDATE finance_key_approval_candidate
                     SET consumed_at=clock_timestamp()
                   WHERE approval_id=%s AND namespace=%s
                     AND requester_subject=%s AND approver_subject=%s
                     AND proposal_sha256=%s AND expires_at=%s
                     AND to_timestamp(expires_at) > clock_timestamp()
                     AND to_timestamp(expires_at) <= clock_timestamp() + interval '15 minutes'
                     AND consumed_at IS NULL
                   RETURNING approval_id""",
                (approval_id, self.namespace, expected.requester_subject,
                 expected.approver_subject, expected.proposal_sha256,
                 expected.expires_at),
            ).fetchone()
            if row is None:
                return False
            self.conn.execute(
                """INSERT INTO finance_key_approval_audit_candidate
                     (approval_id, action) VALUES (%s, 'consumed')""",
                (approval_id,),
            )
        return True
