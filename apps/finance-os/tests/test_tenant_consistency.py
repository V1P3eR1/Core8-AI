"""PostgreSQL tenant consistency contract on disposable sandbox CI database."""
import os
import unittest
from uuid import uuid4

try:
    import psycopg
except ImportError:
    psycopg = None


@unittest.skipUnless(psycopg is not None and bool(os.getenv("DATABASE_URL")),
                     "requires disposable PostgreSQL sandbox DATABASE_URL")
class TenantConsistencyTests(unittest.TestCase):
    def test_activity_cannot_relabel_another_tenants_event(self):
        marker = uuid4().hex
        tenant_a, tenant_b = "ci_a_" + marker, "ci_b_" + marker
        event_id = "evt_tenant_" + marker
        dsn = os.environ["DATABASE_URL"]
        try:
            with psycopg.connect(dsn) as db:
                for tenant in (tenant_a, tenant_b):
                    db.execute(
                        "INSERT INTO finance_organizations (id, legal_name) VALUES (%s,%s)",
                        (tenant, "CI test tenant"),
                    )
                db.execute("""
                    INSERT INTO finance_stripe_event_inbox
                    (event_id, organization_id, event_type, source_object_id, event_created)
                    VALUES (%s,%s,'invoice.paid',%s,now())
                """, (event_id, tenant_a, "in_" + marker))
                with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                    with db.transaction():
                        db.execute("""
                            INSERT INTO finance_activity
                            (stripe_event_id, organization_id, event_type, source_object_id)
                            VALUES (%s,%s,'invoice.paid',%s)
                        """, (event_id, tenant_b, "in_" + marker))
                db.execute("""
                    INSERT INTO finance_activity
                    (stripe_event_id, organization_id, event_type, source_object_id)
                    VALUES (%s,%s,'invoice.paid',%s)
                """, (event_id, tenant_a, "in_" + marker))
                self.assertEqual(
                    db.execute("SELECT organization_id FROM finance_activity WHERE stripe_event_id=%s",
                               (event_id,)).fetchone()[0],
                    tenant_a,
                )
        finally:
            with psycopg.connect(dsn) as db:
                db.execute("DELETE FROM finance_activity WHERE stripe_event_id=%s", (event_id,))
                db.execute("DELETE FROM finance_stripe_event_inbox WHERE event_id=%s", (event_id,))
                db.execute("DELETE FROM finance_organizations WHERE id IN (%s,%s)",
                           (tenant_a, tenant_b))


if __name__ == "__main__":
    unittest.main()
