-- Disposable sandbox-only membership candidate. NOT a production migration.
-- Provisioning, OIDC trust, revocation, auditing and application DB role
-- privileges are not implemented. Do not apply on shared/live databases.
CREATE TABLE finance_membership_candidate (
    subject_id text NOT NULL,
    organization_id text NOT NULL REFERENCES finance_organizations(id),
    role text NOT NULL CHECK (role IN ('viewer','analyst','operator')),
    enabled boolean NOT NULL DEFAULT false,
    PRIMARY KEY(subject_id, organization_id)
);
REVOKE ALL ON finance_membership_candidate FROM PUBLIC;
-- NO privileges are granted here: only a trusted admin can provision
-- membership. A future read-only resolver needs a narrowly scoped role.
