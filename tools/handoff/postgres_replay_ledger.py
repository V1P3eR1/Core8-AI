"""PostgreSQL-backed, cross-runner at-most-once reservation for review artifacts.

Offline component. A caller must supply a trusted PostgreSQL connection factory.
This does not authorize an AI run, artifact publication, merge, or deployment.
No lease expiration, delete, or automatic retry of ambiguous writes is offered.
"""
import re

from replay_ledger import ReplayBlocked

REPO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")
MAX_BIGINT = 2**63 - 1

CREATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS core8_replay_reservations (
  repo TEXT NOT NULL,
  task_digest CHAR(64) NOT NULL,
  run_id BIGINT NOT NULL CHECK (run_id > 0),
  artifact_id BIGINT NOT NULL CHECK (artifact_id > 0),
  patch_sha256 CHAR(64) NOT NULL,
  state TEXT NOT NULL DEFAULT 'RESERVED'
    CHECK (state IN ('RESERVED', 'CONSUMED')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  consumed_at TIMESTAMPTZ,
  PRIMARY KEY (repo, task_digest),
  UNIQUE (repo, run_id, artifact_id),
  CHECK (task_digest ~ '^[a-f0-9]{64}$'),
  CHECK (patch_sha256 ~ '^[a-f0-9]{64}$'),
  CHECK ((state = 'RESERVED' AND consumed_at IS NULL)
      OR (state = 'CONSUMED' AND consumed_at IS NOT NULL))
)
"""

RESERVE_SQL = """
INSERT INTO core8_replay_reservations
    (repo, task_digest, run_id, artifact_id, patch_sha256)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING RETURNING state
"""

CONSUME_SQL = """
UPDATE core8_replay_reservations
SET state = 'CONSUMED', consumed_at = CURRENT_TIMESTAMP
WHERE repo = %s AND task_digest = %s AND run_id = %s
  AND artifact_id = %s AND patch_sha256 = %s AND state = 'RESERVED'
RETURNING state
"""

STATE_SQL = """
SELECT state FROM core8_replay_reservations
WHERE repo = %s AND run_id = %s AND artifact_id = %s
"""


def _id(value):
    if type(value) is not int or not 0 < value <= MAX_BIGINT:
        raise ReplayBlocked("invalid_identifier")
    return value


def _identity(repo, run_id, artifact_id, task_digest, patch_sha256):
    if not isinstance(repo, str) or len(repo) > 200 or not REPO_ID.fullmatch(repo):
        raise ReplayBlocked("invalid_identity")
    if not isinstance(task_digest, str) or not HEX64.fullmatch(task_digest):
        raise ReplayBlocked("invalid_task_digest")
    if not isinstance(patch_sha256, str) or not HEX64.fullmatch(patch_sha256):
        raise ReplayBlocked("invalid_patch_sha256")
    return (repo, task_digest, _id(run_id), _id(artifact_id), patch_sha256)


class PostgresReplayLedger:
    """Requires a trusted psycopg-compatible connection factory.

    The connection context manager MUST commit on normal exit and rollback on
    exceptions. A connection must not auto-commit before that context exits.
    All writes are non-idempotent at the transport boundary: never blindly
    retry a timed-out or disconnected transaction.
    """
    def __init__(self, connection_factory):
        if not callable(connection_factory):
            raise ReplayBlocked("missing_trusted_database_connection")
        self._connect = connection_factory

    def install_schema(self):
        """Explicit installation by privileged migration operator, not per run."""
        with self._connect() as db:
            with db.cursor() as cur:
                cur.execute(CREATE_SCHEMA)

    def reserve(self, *, repo, run_id, artifact_id, task_digest, patch_sha256):
        fields = _identity(repo, run_id, artifact_id, task_digest, patch_sha256)
        with self._connect() as db:
            with db.cursor() as cur:
                cur.execute(RESERVE_SQL, fields)
                if cur.fetchone() != ("RESERVED",):
                    raise ReplayBlocked("already_reserved")

    def mark_consumed(self, *, repo, run_id, artifact_id, task_digest, patch_sha256):
        fields = _identity(repo, run_id, artifact_id, task_digest, patch_sha256)
        with self._connect() as db:
            with db.cursor() as cur:
                cur.execute(CONSUME_SQL, fields)
                if cur.fetchone() != ("CONSUMED",):
                    raise ReplayBlocked("missing_mismatched_or_consumed")

    def state(self, *, repo, run_id, artifact_id):
        if not isinstance(repo, str) or len(repo) > 200 or not REPO_ID.fullmatch(repo):
            raise ReplayBlocked("invalid_identity")
        fields = (repo, _id(run_id), _id(artifact_id))
        with self._connect() as db:
            with db.cursor() as cur:
                cur.execute(STATE_SQL, fields)
                row = cur.fetchone()
                if row is not None and (type(row) is not tuple or row[0] not in ("RESERVED", "CONSUMED")):
                    raise ReplayBlocked("invalid_database_state")
                return row[0] if row else None
