"""Tenant query policy and SQL-scope tests without a real DB or live API."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tenant_access import VerifiedFinancePrincipal, FinanceAccessDenied
from tenant_queries import read_inbox_status_counts


class RecordingConnection:
    def __init__(self):
        self.sql = None
        self.params = None

    def execute(self, sql, params):
        self.sql, self.params = sql, params
        return self

    def fetchall(self):
        return [("received", 2), ("processed", 1)]


class TenantQueryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.conn = RecordingConnection()
        self.viewer = VerifiedFinancePrincipal("user_abc", "tenant_alpha", "viewer")

    def test_exact_tenant_in_query_and_aggregates(self):
        output = read_inbox_status_counts(
            self.conn, principal=self.viewer, tenant_id="tenant_alpha"
        )
        self.assertEqual(output, {"received": 2, "processed": 1})
        self.assertIn("WHERE organization_id = %s", self.conn.sql)
        self.assertEqual(self.conn.params, ("tenant_alpha",))
        self.assertNotIn("tenant_alpha", self.conn.sql)

    def test_cross_tenant_denied_before_database_access(self):
        with self.assertRaises(FinanceAccessDenied):
            read_inbox_status_counts(
                self.conn, principal=self.viewer, tenant_id="tenant_beta"
            )
        self.assertIsNone(self.conn.sql)

    def test_untrusted_or_inactive_principal_denied_before_database_access(self):
        cases = [
            None,
            {"subject": "user_abc", "tenant_id": "tenant_alpha", "role": "operator"},
            VerifiedFinancePrincipal("user_abc", "tenant_alpha", "viewer", False),
        ]
        for candidate in cases:
            self.conn = RecordingConnection()
            with self.subTest(candidate=candidate):
                with self.assertRaises(FinanceAccessDenied):
                    read_inbox_status_counts(
                        self.conn, principal=candidate, tenant_id="tenant_alpha"
                    )
                self.assertIsNone(self.conn.sql)


if __name__ == "__main__":
    unittest.main()
