-- Core8-AI lead intake idempotency: PROPOSAL ONLY, NOT A DEPLOYED MIGRATION.
-- Tenant ID MUST come from authenticated server context, never a submitted payload.
-- The primary key makes (tenant, source, submission) unique atomically.
-- This schema is intentionally isolated from existing production migrations.
BEGIN;
CREATE TABLE IF NOT EXISTS core8_lead_intake_idempotency (
  tenant_id text NOT NULL CHECK (length(tenant_id) BETWEEN 1 AND 256),
  source_system text NOT NULL CHECK (source_system IN ('lead_triage','receptionist_demo','social')),
  source_submission_id text NOT NULL CHECK (length(source_submission_id) BETWEEN 1 AND 256),
  lead_id text NOT NULL CHECK (length(lead_id) BETWEEN 1 AND 256),
  payload_sha256 char(64) NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, source_system, source_submission_id),
  UNIQUE (tenant_id, lead_id)
);
COMMIT;

-- Intended transaction shape (pseudocode; use bound parameters, never interpolate):
-- BEGIN;
-- INSERT ... VALUES (:trusted_tenant_id, :source_system, :submission_id,
--                    :lead_id, :payload_sha256)
-- ON CONFLICT (tenant_id, source_system, source_submission_id) DO NOTHING
-- RETURNING lead_id, payload_sha256;
-- If inserted: create lead in the SAME transaction, then COMMIT.
-- If conflict: SELECT lead_id,payload_sha256 for matching key;
-- compare payload hash in constant-time at application boundary where relevant;
-- return existing lead for matching payload, or 409 on conflicting payload.
-- ROLLBACK on any failure.
--
-- IMPORTANT: This proposal does not implement authenticated tenant context,
-- authorization, RLS, actual transaction wiring, retry policy or retention.
-- Review DB privileges, data minimization, canonical hashing and atomic
-- transaction boundaries before converting this into a production migration.
