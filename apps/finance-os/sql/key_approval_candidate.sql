-- Disposable CI candidate ONLY. Not a production migration.
-- Provisioning, operator identity, retention and external anti-rollback are TBD.
CREATE TABLE IF NOT EXISTS finance_key_approval_candidate (
  approval_id text PRIMARY KEY,
  namespace text NOT NULL,
  requester_subject text NOT NULL,
  approver_subject text NOT NULL,
  proposal_sha256 text NOT NULL,
  expires_at bigint NOT NULL,
  consumed_at timestamptz,
  CHECK (requester_subject <> approver_subject),
  CHECK (proposal_sha256 ~ '^[0-9a-f]{64}$')
);
CREATE TABLE IF NOT EXISTS finance_key_approval_audit_candidate (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  approval_id text NOT NULL REFERENCES finance_key_approval_candidate(approval_id),
  action text NOT NULL CHECK (action IN ('consumed')),
  recorded_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON finance_key_approval_candidate FROM PUBLIC;
REVOKE ALL ON finance_key_approval_audit_candidate FROM PUBLIC;
-- No application role or untrusted client gets INSERT/UPDATE/DELETE.
