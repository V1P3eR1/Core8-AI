-- Disposable Finance OS CI ONLY. Append-only audit table guard candidate.
-- This is database-local defense-in-depth, NOT external tamper-evident audit.
-- Owners/superusers can disable/drop triggers or restore older database backups.
CREATE OR REPLACE FUNCTION finance_key_audit_reject_mutation_candidate()
RETURNS trigger
LANGUAGE plpgsql
AS $guard$
BEGIN
  RAISE EXCEPTION 'finance approval audit is append-only'
    USING ERRCODE = '42501';
END
$guard$;

CREATE TRIGGER finance_key_audit_no_modify_candidate
BEFORE UPDATE OR DELETE ON finance_key_approval_audit_candidate
FOR EACH ROW EXECUTE FUNCTION finance_key_audit_reject_mutation_candidate();

CREATE TRIGGER finance_key_audit_no_truncate_candidate
BEFORE TRUNCATE ON finance_key_approval_audit_candidate
FOR EACH STATEMENT EXECUTE FUNCTION finance_key_audit_reject_mutation_candidate();
