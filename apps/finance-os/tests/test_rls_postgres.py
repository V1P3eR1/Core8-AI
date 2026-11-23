"""Disposable PostgreSQL RLS integration test; no live tenant data.

This test applies the RLS *candidate* to the existing sandbox inbox and
activity tables only while the test is running, then removes every policy.
No HTTP endpoint, Stripe integration or production migration is enabled.
"""
import os
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import psycopg
    from psycopg import errors
    READY = os.getenv("APP_ENV") == "test" and bool(os.getenv("DATABASE_URL"))
except ImportError:
    READY = False

ROOT = Path(__file__).resolve().parents[1]
ROLE_A = "finance_ci_rls_alpha"
ROLE_B = "finance_ci_rls_beta"


@unittest.skipUnless(READY, "only disposable PostgreSQL test environment")
class ReadOnlyRlsIntegration(unittest.TestCase):
    def test_read_isolation_and_write_denial_for_database_roles(self):
        # This test must run only with the disposable CI postgres superuser.
        # Do NOT run against an existing shared database.
        suffix = uuid4().hex
        tenant_a, tenant_b = "ci_rls_a_" + suffix, "ci_rls_b_" + suffix
        event_a, event_b = "evt_rls_a_" + suffix, "evt_rls_b_" + suffix
        dsn = os.environ["DATABASE_URL"]
        with psycopg.connect(dsn) as conn:
            is_super = conn.execute(
                "SELECT rolsuper FROM pg_roles WHERE rolname=current_user"
            ).fetchone()[0]
            if not is_super:
                self.skipTest("requires disposable CI superuser to provision test roles")
            # Create test roles and fixtures before activating RLS.
            conn.execute("CREATE ROLE finance_ci_rls_alpha NOLOGIN NOSUPERUSER NOBYPASSRLS")
            conn.execute("CREATE ROLE finance_ci_rls_beta NOLOGIN NOSUPERUSER NOBYPASSRLS")
            for org in (tenant_a, tenant_b):
                conn.execute("INSERT INTO finance_organizations(id,legal_name) VALUES (%s,'CI Only')", (org,))
            for eid, org in ((event_a, tenant_a), (event_b, tenant_b)):
                conn.execute("""
                    INSERT INTO finance_stripe_event_inbox
                        (event_id,organization_id,event_type,source_object_id,event_created)
                    VALUES (%s,%s,'invoice.paid','in_fixture',now())
                """, (eid, org))
                conn.execute("""
                    INSERT INTO finance_activity
                        (stripe_event_id,organization_id,event_type,source_object_id)
                    VALUES (%s,%s,'invoice.paid','in_fixture')
                """, (eid, org))
        try:
            source = (ROOT / "sql" / "rls_readonly_candidate.sql").read_text()
            with psycopg.connect(dsn) as admin:
                # The candidate deliberately has no procedural SQL blocks.
                for stmt in source.split(";"):
                    # Remove SQL comments so statement splitting stays simple.
                    s = "\n".join(line for line in stmt.splitlines()
                                  if not line.strip().startswith("--")).strip()
                    if s:
                        admin.execute(s)
                for role in (ROLE_A, ROLE_B):
                    # The restricted role can inspect bindings but cannot edit them.
                    admin.execute("GRANT SELECT ON finance_rls_role_bindings TO " + role)
                    admin.execute("GRANT SELECT ON finance_stripe_event_inbox TO " + role)
                    admin.execute("GRANT SELECT ON finance_activity TO " + role)
                admin.execute("INSERT INTO finance_rls_role_bindings(db_role,organization_id) VALUES (%s,%s),(%s,%s)",
                              (ROLE_A, tenant_a, ROLE_B, tenant_b))
            for role, expected_id, denied_id in (
                (ROLE_A, event_a, event_b), (ROLE_B, event_b, event_a)
            ):
                with psycopg.connect(dsn) as db:
                    with db.transaction():
                        db.execute("SET LOCAL ROLE " + role)
                        ids = {row[0] for row in db.execute(
                            "SELECT event_id FROM finance_stripe_event_inbox WHERE event_id IN (%s,%s)",
                            (event_a, event_b)
                        ).fetchall()}
                        self.assertEqual(ids, {expected_id})
                        activities = {row[0] for row in db.execute(
                            "SELECT stripe_event_id FROM finance_activity WHERE stripe_event_id IN (%s,%s)",
                            (event_a, event_b)
                        ).fetchall()}
                        self.assertEqual(activities, {expected_id})
                        with self.assertRaises(errors.InsufficientPrivilege):
                            with db.transaction():
                                db.execute(
                                    "UPDATE finance_stripe_event_inbox SET status='failed' WHERE event_id=%s",
                                    (expected_id,)
                                )
                        with self.assertRaises(errors.InsufficientPrivilege):
                            with db.transaction():
                                db.execute("INSERT INTO finance_rls_role_bindings(db_role,organization_id) VALUES (%s,%s)",
                                           (role, tenant_b if role == ROLE_A else tenant_a))
        finally:
            # Remove security policies first, then tenant fixtures and test roles.
            # Keep this test confined to disposable CI; cleanup is not a
            # substitute for provisioning and migration management.
            with psycopg.connect(dsn) as db:
                db.execute("DROP POLICY IF EXISTS finance_ci_inbox_read ON finance_stripe_event_inbox")
                db.execute("DROP POLICY IF EXISTS finance_ci_activity_read ON finance_activity")
                for table in ("finance_stripe_event_inbox", "finance_activity"):
                    db.execute("ALTER TABLE " + table + " NO FORCE ROW LEVEL SECURITY")
                    db.execute("ALTER TABLE " + table + " DISABLE ROW LEVEL SECURITY")
                db.execute("DELETE FROM finance_activity WHERE stripe_event_id IN (%s,%s)", (event_a, event_b))
                db.execute("DELETE FROM finance_stripe_event_inbox WHERE event_id IN (%s,%s)", (event_a, event_b))
                db.execute("DROP TABLE IF EXISTS finance_rls_role_bindings")
                db.execute("DELETE FROM finance_organizations WHERE id IN (%s,%s)", (tenant_a, tenant_b))
                for role in (ROLE_A, ROLE_B):
                    db.execute("REVOKE ALL ON finance_activity FROM " + role)
                    db.execute("REVOKE ALL ON finance_stripe_event_inbox FROM " + role)
                    db.execute("DROP ROLE IF EXISTS " + role)


if __name__ == "__main__":
    unittest.main()
