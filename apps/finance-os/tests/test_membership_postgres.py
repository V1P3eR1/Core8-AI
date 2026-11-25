"""Disposable PostgreSQL integration for the membership candidate only."""
import os
import sys
import unittest
from pathlib import Path
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import psycopg
    READY = os.getenv("APP_ENV") == "test" and bool(os.getenv("DATABASE_URL"))
except ImportError:
    READY = False
from membership_candidate import TrustedSubject, resolve_finance_membership
from tenant_access import FinanceAccessDenied, require_finance_permission

@unittest.skipUnless(READY, "disposable CI Postgres only")
class MembershipPostgresTests(unittest.TestCase):
    def test_role_revocation_and_cross_tenant_resolution(self):
        tenant_a = "ci_member_a_" + uuid4().hex
        tenant_b = "ci_member_b_" + uuid4().hex
        subject = TrustedSubject("sub_ci_" + uuid4().hex)
        with psycopg.connect(os.environ["DATABASE_URL"]) as db:
            # Entire candidate schema and synthetic records are rolled back.
            source = (Path(__file__).resolve().parents[1] /
                      "sql/membership_candidate.sql").read_text()
            for statement in source.split(";"):
                clean = "\n".join(line for line in statement.splitlines()
                                  if not line.lstrip().startswith("--")).strip()
                if clean:
                    db.execute(clean)
            for tenant in (tenant_a, tenant_b):
                db.execute("INSERT INTO finance_organizations(id,legal_name) VALUES (%s,%s)",
                           (tenant, "CI synthetic org"))
            db.execute("""
                INSERT INTO finance_membership_candidate
                  (subject_id, organization_id, role, enabled)
                VALUES (%s,%s,'viewer',true),(%s,%s,'operator',false)
            """, (subject.value, tenant_a, subject.value, tenant_b))
            principal = resolve_finance_membership(db, subject=subject, tenant_id=tenant_a)
            self.assertEqual(principal.role, "viewer")
            with self.assertRaises(FinanceAccessDenied):
                resolve_finance_membership(db, subject=subject, tenant_id=tenant_b)
            with self.assertRaises(FinanceAccessDenied):
                require_finance_permission(principal, tenant_id=tenant_b,
                                           action="finance:read")
            db.execute("""UPDATE finance_membership_candidate SET enabled=false
                          WHERE subject_id=%s AND organization_id=%s""",
                       (subject.value, tenant_a))
            with self.assertRaises(FinanceAccessDenied):
                resolve_finance_membership(db, subject=subject, tenant_id=tenant_a)
            db.execute("""UPDATE finance_membership_candidate SET enabled=true,role='analyst'
                          WHERE subject_id=%s AND organization_id=%s""",
                       (subject.value, tenant_b))
            new_principal = resolve_finance_membership(db, subject=subject, tenant_id=tenant_b)
            self.assertEqual(new_principal.role, "analyst")
            with self.assertRaises(FinanceAccessDenied):
                require_finance_permission(new_principal, tenant_id=tenant_b,
                                           action="finance:operate")
            db.rollback()  # no candidate table, membership or tenant remains

if __name__ == "__main__":
    unittest.main()
