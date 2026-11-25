"""Finance OS authorization policy regression tests; no real identity provider."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tenant_access import (
    FinanceAccessDenied, VerifiedFinancePrincipal, require_finance_permission,
)


class FinanceTenantAccessTests(unittest.TestCase):
    def principal(self, role="viewer", tenant_id="tenant_alpha", **kwargs):
        return VerifiedFinancePrincipal(
            subject="user_123", tenant_id=tenant_id, role=role, **kwargs
        )

    def allow(self, principal, action="finance:read", tenant_id="tenant_alpha"):
        require_finance_permission(principal, action=action, tenant_id=tenant_id)

    def deny(self, principal, action="finance:read", tenant_id="tenant_alpha"):
        with self.assertRaises(FinanceAccessDenied):
            self.allow(principal, action=action, tenant_id=tenant_id)

    def test_viewer_read_only(self):
        self.allow(self.principal())
        for action in ("finance:review", "finance:operate"):
            with self.subTest(action=action):
                self.deny(self.principal(), action=action)

    def test_analyst_cannot_operate(self):
        self.allow(self.principal(role="analyst"), action="finance:review")
        self.deny(self.principal(role="analyst"), action="finance:operate")

    def test_operator_only_for_exact_tenant(self):
        p = self.principal(role="operator")
        for action in ("finance:read", "finance:review", "finance:operate"):
            self.allow(p, action=action)
            self.deny(p, action=action, tenant_id="tenant_beta")

    def test_missing_or_unverified_principal_is_rejected(self):
        for candidate in (None, {}, {"subject": "user_123", "role": "operator"},
                          "user_123", False):
            with self.subTest(candidate=candidate):
                self.deny(candidate)

    def test_role_names_are_exact_not_case_insensitive(self):
        for role in ("Operator", "admin", "root", "", None, 0, [], {}):
            with self.subTest(role=role):
                self.deny(self.principal(role=role))

    def test_disabled_or_malformed_identity_denied(self):
        self.deny(self.principal(enabled=False))
        self.deny(self.principal(enabled="true"))
        self.deny(VerifiedFinancePrincipal(subject="", tenant_id="tenant_alpha",
                                         role="operator"))
        self.deny(VerifiedFinancePrincipal(subject="user_123", tenant_id="",
                                         role="operator"))

    def test_reject_tenant_id_injection(self):
        for tenant in ("tenant_beta", "tenant_alpha ", "tenant_alpha/../../other",
                       "", None, "tenant_🧪"):
            with self.subTest(tenant=tenant):
                self.deny(self.principal(), tenant_id=tenant)

    def test_unknown_permissions_denied(self):
        for action in ("finance:write", "finance:delete", "finance:operate:any",
                       "", None, [], {}):
            with self.subTest(action=action):
                self.deny(self.principal(role="operator"), action=action)


if __name__ == "__main__":
    unittest.main()
