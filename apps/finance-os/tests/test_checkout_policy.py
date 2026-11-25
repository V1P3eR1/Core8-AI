import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checkout_policy import CheckoutIntent, CatalogPrice, validate_checkout_intent

class CheckoutPolicyTests(unittest.TestCase):
    def setUp(self):
        self.price=CatalogPrice("price_test_abc", "subscription", "USD")
        self.base=dict(
            tenant_id="tenant_a",catalog_price_id="price_test_abc",quantity=1,
            mode="subscription",success_url="https://app.core8-ai.com/success",
            cancel_url="https://app.core8-ai.com/cancel")
        self.kw=dict(authenticated_tenant_id="tenant_a",
                     approved_catalog={self.price.price_id:self.price},
                     allowed_redirect_hosts=frozenset({"app.core8-ai.com"}))
    def call(self,**changes):
        return validate_checkout_intent(CheckoutIntent(**(self.base|changes)),**self.kw)
    def test_review_only(self):
        result=self.call()
        self.assertFalse(result["approved_for_execution"])
        self.assertEqual(result["environment"],"sandbox")
        self.assertTrue(result["requires_human_approval"])
    def test_cross_tenant_rejected(self):
        with self.assertRaises(PermissionError): self.call(tenant_id="tenant_b")
    def test_unknown_price_rejected(self):
        with self.assertRaises(ValueError): self.call(catalog_price_id="price_unapproved")
    def test_wrong_price_mode_rejected(self):
        with self.assertRaises(ValueError): self.call(mode="payment")
    def test_invalid_quantity(self):
        for quantity in (0,101,True,1.2):
            with self.subTest(quantity=quantity),self.assertRaises(ValueError):
                self.call(quantity=quantity)
    def test_redirect_external_rejected(self):
        for url in ("https://evil.example/checkout","http://app.core8-ai.com/ok",
                    "https://app.core8-ai.com.evil.example/ok",
                    "https://user@app.core8-ai.com/ok",
                    "https://app.core8-ai.com:8443/ok"):
            with self.subTest(url=url), self.assertRaises(ValueError): self.call(success_url=url)
    def test_disabled_price_rejected(self):
        self.kw["approved_catalog"]={"price_test_abc":CatalogPrice("price_test_abc","subscription","USD",False)}
        with self.assertRaises(ValueError):self.call()
    def test_no_tenant_context_rejected(self):
        self.kw["authenticated_tenant_id"]=""
        with self.assertRaises(PermissionError):self.call()
    def test_empty_redirect_hosts_rejected(self):
        self.kw["allowed_redirect_hosts"]=frozenset()
        with self.assertRaises(ValueError):self.call()
if __name__ == "__main__":unittest.main()
