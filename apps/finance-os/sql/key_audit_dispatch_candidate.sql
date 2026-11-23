-- Disposable CI-only evolution of the candidate transactional audit outbox.
-- No network delivery, production migration, credentials or authorization grant.
ALTER TABLE finance_key_audit_outbox_candidate
  ADD COLUMN lease_token text,
  ADD COLUMN lease_until timestamptz,
  ADD COLUMN next_attempt_at timestamptz;
ALTER TABLE finance_key_audit_outbox_candidate
  ADD CONSTRAINT finance_key_audit_lease_pair_candidate
  CHECK ((lease_token IS NULL) = (lease_until IS NULL));
CREATE INDEX finance_key_audit_due_candidate
  ON finance_key_audit_outbox_candidate (next_attempt_at, audit_id)
  WHERE delivered_at IS NULL;
-- Acknowledgments are locally recorded, not externally proven delivery.
