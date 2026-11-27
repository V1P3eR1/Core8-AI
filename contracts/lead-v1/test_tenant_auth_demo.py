import importlib.util
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location("policy",Path(__file__).with_name("tenant_auth_demo.py"))
policy=importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
identity={"verified":True,"sub":"user-A","role":"admin"}
memberships=[{"user_id":"user-A","tenant_id":"tenant-A","active":True,
              "permissions":["lead:intake"]}]

class TenantAuthTests(unittest.TestCase):
    def check(self, **changes):
        args=dict(identity=identity,requested_tenant_id="tenant-A",memberships=memberships)
        args.update(changes)
        return policy.resolve_tenant(**args)
    def test_explicit_membership_grants_only_its_tenant(self):
        self.assertEqual(self.check(),{"ok":True,"trusted_tenant_id":"tenant-A"})
    def test_admin_without_membership_is_denied(self):
        self.assertEqual(self.check(requested_tenant_id="tenant-B")["reason"],"forbidden")
    def test_unverified_identity_is_denied(self):
        self.assertEqual(self.check(identity={"sub":"user-A","role":"admin"})["reason"],"unauthenticated")
    def test_missing_identity_is_denied(self):
        self.assertEqual(self.check(identity=None)["reason"],"unauthenticated")
    def test_other_users_membership_is_denied(self):
        self.assertEqual(self.check(identity={"verified":True,"sub":"user-B"})["reason"],"forbidden")
    def test_inactive_membership_is_denied(self):
        inactive=[dict(memberships[0],active=False)]
        self.assertEqual(self.check(memberships=inactive)["reason"],"forbidden")
    def test_missing_permission_is_denied(self):
        no_permission=[dict(memberships[0],permissions=["lead:read"])]
        self.assertEqual(self.check(memberships=no_permission)["reason"],"forbidden")
    def test_bad_membership_data_fails_closed(self):
        self.assertEqual(self.check(memberships=None)["reason"],"forbidden")
        self.assertEqual(self.check(memberships=[None,{}])["reason"],"forbidden")
    def test_empty_tenant_is_rejected(self):
        self.assertEqual(self.check(requested_tenant_id="")["reason"],"invalid_tenant")

if __name__=="__main__":
    unittest.main()
