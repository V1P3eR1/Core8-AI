-- REVIEW-ONLY RLS candidate for disposable sandbox databases.
-- DO NOT run on existing production/shared databases. This is not a
-- migration: role provisioning, bootstrapping, rollback and operational
-- writer/worker access are intentionally unresolved.
--
-- Trusted database administrators must provision role-to-tenant bindings
-- after independently verifying membership. Never derive bindings from
-- request headers, unverified JWT claims or Stripe event metadata.
CREATE TABLE IF NOT EXISTS finance_rls_role_bindings (
  db_role name NOT NULL,
  organization_id text NOT NULL REFERENCES finance_organizations(id),
  PRIMARY KEY (db_role, organization_id)
);
REVOKE ALL ON finance_rls_role_bindings FROM PUBLIC;

ALTER TABLE finance_stripe_event_inbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE finance_stripe_event_inbox FORCE ROW LEVEL SECURITY;
CREATE POLICY finance_ci_inbox_read ON finance_stripe_event_inbox
  FOR SELECT TO PUBLIC
  USING (
    EXISTS (
      SELECT 1 FROM finance_rls_role_bindings b
      WHERE b.db_role = current_user
        AND b.organization_id = finance_stripe_event_inbox.organization_id
    )
  );

ALTER TABLE finance_activity ENABLE ROW LEVEL SECURITY;
ALTER TABLE finance_activity FORCE ROW LEVEL SECURITY;
CREATE POLICY finance_ci_activity_read ON finance_activity
  FOR SELECT TO PUBLIC
  USING (
    EXISTS (
      SELECT 1 FROM finance_rls_role_bindings b
      WHERE b.db_role = current_user
        AND b.organization_id = finance_activity.organization_id
    )
  );
-- No INSERT/UPDATE/DELETE policies. Read-only roles are not writers.
-- A privileged trusted ingress/worker implementation and migrations
-- require a separate security review before any non-test rollout.
