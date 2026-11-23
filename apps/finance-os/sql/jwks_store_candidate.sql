-- SANDBOX TEST CANDIDATE ONLY. Never run on a shared or production DB.
-- Not a migration: trusted role provisioning, backups, audit and disaster
-- recovery have not been specified or approved.
CREATE TABLE IF NOT EXISTS finance_jwks_store_candidate (
    namespace text PRIMARY KEY,
    generation bigint NOT NULL CHECK (generation >= 1),
    signed_snapshot bytea NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON finance_jwks_store_candidate FROM PUBLIC;
-- NO grants to the running API / webhook / worker. Test superuser only.
-- Database generation is transactionally consistent with the snapshot, but
-- cannot detect whole-database rollback. An independent trusted monotonic
-- watermark must be committed before treating recovered state as authoritative.
