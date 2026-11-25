"""Regression tests for review-only merchant binding adapter."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from merchant_binding import resolve_single_merchant


class MerchantBindingTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "FINANCE_WEBHOOK_ACCOUNT_ID": "acct_sandboxA123",
            "FINANCE_WEBHOOK_TENANT_ID": "tenant_alpha",
        }

    def test_explicit_sandbox_binding(self):
        account, mapping = resolve_single_merchant({"id": "evt_1"}, environ=self.env)
        self.assertEqual(account, "acct_sandboxA123")
        self.assertEqual(mapping, {"acct_sandboxA123": "tenant_alpha"})

    def test_missing_account_fails_closed(self):
        env = dict(self.env)
        env.pop("FINANCE_WEBHOOK_ACCOUNT_ID")
        with self.assertRaises(ValueError):
            resolve_single_merchant({}, environ=env)

    def test_missing_tenant_fails_closed(self):
        env = dict(self.env)
        env.pop("FINANCE_WEBHOOK_TENANT_ID")
        with self.assertRaises(ValueError):
            resolve_single_merchant({}, environ=env)

    def test_invalid_configuration_fails_closed(self):
        for key, value in [
            ("FINANCE_WEBHOOK_ACCOUNT_ID", "not_a_stripe_account"),
            ("FINANCE_WEBHOOK_TENANT_ID", " "),
        ]:
            with self.subTest(key=key):
                env = dict(self.env)
                env[key] = value
                with self.assertRaises(ValueError):
                    resolve_single_merchant({}, environ=env)

    def test_connect_event_rejected_even_when_account_matches(self):
        with self.assertRaises(ValueError):
            resolve_single_merchant({"account": "acct_sandboxA123"}, environ=self.env)

    def test_untrusted_metadata_never_changes_binding(self):
        account, mapping = resolve_single_merchant(
            {"metadata": {"tenant_id": "tenant_beta"}}, environ=self.env
        )
        self.assertEqual(mapping[account], "tenant_alpha")

    def test_non_mapping_event_rejected(self):
        with self.assertRaises(ValueError):
            resolve_single_merchant(None, environ=self.env)


if __name__ == "__main__":
    unittest.main()
