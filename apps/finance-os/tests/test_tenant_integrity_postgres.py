"""Real PostgreSQL tests of the current Finance OS tenant integrity boundaries.

Only disposable test database; no Stripe calls or customer data.
These tests prove FK and event-ID uniqueness, NOT OIDC/RBAC or RLS.
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
    DB_READY = bool(os.getenv("DATABASE_URL")) and os.getenv("APP_ENV") == "test"
except ImportError:
    DB_READY = False


@unittest.skipUnless(DB_READY, "requires explicitly configured disposable PostgreSQL test DB")
class TenantIntegrityPostgresTests(unittest.TestCase):
    def setUp(self):
        self.tenant_a = "ci_tenant_a_" + uuid4().hex
        self.tenant_b = "ci_tenant_b_" + uuid4().hex
        self.event_id = "evt_tenant_" + uuid4().hex
        self.db = psycopg.connect(os.environ["DATABASE_URL"])
        # Use an outer transaction and rollback for total test isolation.
        # Never run these tests against production.
        for tenant in (self.tenant_a, self.tenant_b):
            self.db.execute(
                "INSERT INTO finance_organizations (id, legal_name) VALUES (%s, %s)",
                (tenant, "CI sandbox tenant"),
            )
        self.db.execute(
            """INSERT INTO finance_stripe_event_inbox
               (event_id, organization_id, event_type, source_object_id, event_created)
               VALUES (%s, %s, 'invoice.paid', 'in_ci_only', now())""",
            (self.event_id, self.tenant_a),
        )

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_cross_tenant_activity_reference_rejected(self):
        """Composite FK prevents tenant B from referencing tenant A's inbox event."""
        with self.assertRaises(errors.ForeignKeyViolation):
            with self.db.transaction():
                self.db.execute(
                    """INSERT INTO finance_activity
                       (stripe_event_id, organization_id, event_type, source_object_id)
                       VALUES (%s, %s, 'invoice.paid', 'in_ci_only')""",
                    (self.event_id, self.tenant_b),
                )
        # Existing inbox attribution is unchanged.
        org = self.db.execute(
            "SELECT organization_id FROM finance_stripe_event_inbox WHERE event_id=%s",
            (self.event_id,),
        ).fetchone()[0]
        self.assertEqual(org, self.tenant_a)

    def test_event_id_cannot_be_reused_by_another_tenant(self):
        """Global event-id primary key must not let a duplicate rewrite tenant ownership."""
        with self.assertRaises(errors.UniqueViolation):
            with self.db.transaction():
                self.db.execute(
                    """INSERT INTO finance_stripe_event_inbox
                       (event_id, organization_id, event_type, source_object_id, event_created)
                       VALUES (%s, %s, 'invoice.paid', 'in_other', now())""",
                    (self.event_id, self.tenant_b),
                )
        org, source = self.db.execute(
            """SELECT organization_id, source_object_id
               FROM finance_stripe_event_inbox WHERE event_id=%s""",
            (self.event_id,),
        ).fetchone()
        self.assertEqual((org, source), (self.tenant_a, "in_ci_only"))

    def test_matching_tenant_activity_reference_succeeds(self):
        self.db.execute(
            """INSERT INTO finance_activity
               (stripe_event_id, organization_id, event_type, source_object_id)
               VALUES (%s, %s, 'invoice.paid', 'in_ci_only')""",
            (self.event_id, self.tenant_a),
        )
        self.assertEqual(
            self.db.execute(
                "SELECT organization_id FROM finance_activity WHERE stripe_event_id=%s",
                (self.event_id,),
            ).fetchone()[0],
            self.tenant_a,
        )


    def test_tenant_scoped_read_only_aggregate_excludes_other_tenant(self):
        """One tenant's counts never include another tenant's inbox events."""
        from tenant_access import VerifiedFinancePrincipal, FinanceAccessDenied
        from tenant_queries import read_inbox_status_counts

        self.db.execute(
            """INSERT INTO finance_stripe_event_inbox
               (event_id, organization_id, event_type, source_object_id, event_created)
               VALUES (%s, %s, 'invoice.paid', 'in_ci_other', now())""",
            ("evt_other_" + uuid4().hex, self.tenant_b),
        )
        principal_a = VerifiedFinancePrincipal("user_test", self.tenant_a, "viewer")
        principal_b = VerifiedFinancePrincipal("user_test", self.tenant_b, "viewer")
        a_counts = read_inbox_status_counts(
            self.db, principal=principal_a, tenant_id=self.tenant_a
        )
        b_counts = read_inbox_status_counts(
            self.db, principal=principal_b, tenant_id=self.tenant_b
        )
        self.assertEqual(a_counts, {"received": 1})
        self.assertEqual(b_counts, {"received": 1})
        with self.assertRaises(FinanceAccessDenied):
            read_inbox_status_counts(
                self.db, principal=principal_a, tenant_id=self.tenant_b
            )



if __name__ == "__main__":
    unittest.main()
