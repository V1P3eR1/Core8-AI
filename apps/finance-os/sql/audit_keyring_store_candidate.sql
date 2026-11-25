-- Disposable CI ONLY: signed audit signing-key metadata snapshots.
-- This is not a production migration and cannot prevent whole-DB rollback.
-- No signing key bytes live in this table. External floor and KMS required.
CREATE TABLE IF NOT EXISTS finance_audit_keyring_store_candidate (
    namespace text PRIMARY KEY,
    generation bigint NOT NULL CHECK (generation >= 1),
    signed_snapshot bytea NOT NULL CHECK (octet_length(signed_snapshot) BETWEEN 1 AND 16384),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
REVOKE ALL ON finance_audit_keyring_store_candidate FROM PUBLIC;
-- Only test administrator owns table; never grant it to Finance API roles.
