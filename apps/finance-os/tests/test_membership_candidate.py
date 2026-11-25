"""Membership resolution tests. No external identity provider or live database."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from membership_candidate import TrustedSubject, resolve_finance_membership
from tenant_access import FinanceAccessDenied, require_finance_permission

class StubDatabase:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))
        return self

    def fetchall(self):
        return self.rows

class MembershipCandidateTests(unittest.TestCase):
    def lookup(self, rows, subject=None, tenant_id="tenant_alpha"):
        conn = StubDatabase(rows)
        identity = TrustedSubject("sub_example_123") if subject is None else subject
        return conn, resolve_finance_membership(conn, subject=identity,
                                                tenant_id=tenant_id)

    def test_active_membership_controls_access(self):
        conn, principal = self.lookup([("viewer", True)])
        self.assertEqual(principal.tenant_id, "tenant_alpha")
        self.assertEqual(principal.role, "viewer")
        self.assertEqual(conn.calls[0][1], ("sub_example_123", "tenant_alpha"))
        self.assertIn("organization_id = %s", conn.calls[0][0])
        require_finance_permission(principal, tenant_id="tenant_alpha",
                                   action="finance:read")
        with self.assertRaises(FinanceAccessDenied):
            require_finance_permission(principal, tenant_id="tenant_alpha",
                                       action="finance:operate")

    def test_missing_disabled_ambiguous_or_invalid_role_fail_closed(self):
        for rows in ([], [("viewer", False)], [("operator", 1)],
                     [("admin", True)], [("viewer", True), ("operator", True)]):
            with self.subTest(rows=rows):
                with self.assertRaises(FinanceAccessDenied):
                    self.lookup(rows)

    def test_untrusted_subjects_denied_without_sql(self):
        for value in (None, {}, "sub_example_123", TrustedSubject(""),
                      TrustedSubject("bad subject"), TrustedSubject(123)):
            conn = StubDatabase([("operator", True)])
            with self.subTest(value=value):
                with self.assertRaises(FinanceAccessDenied):
                    resolve_finance_membership(
                        conn, subject=value, tenant_id="tenant_alpha")
                self.assertEqual(conn.calls, [])

    def test_invalid_tenant_denied_without_sql(self):
        for tenant in ("", None, "../tenant_beta", "tenant beta"):
            conn = StubDatabase([("operator", True)])
            with self.subTest(tenant=tenant):
                with self.assertRaises(FinanceAccessDenied):
                    resolve_finance_membership(
                        conn, subject=TrustedSubject("sub_example_123"),
                        tenant_id=tenant)
                self.assertEqual(conn.calls, [])

if __name__ == "__main__":
    unittest.main()
