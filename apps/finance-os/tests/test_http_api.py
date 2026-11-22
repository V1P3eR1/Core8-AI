"""HTTP contract tests; no Stripe connection or database required."""
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from fastapi.testclient import TestClient
    from main import app
    HAS_HTTP = True
except ImportError:
    HAS_HTTP = False

@unittest.skipUnless(HAS_HTTP, "FastAPI/httpx not installed")
class TestFinanceWebhookHTTP(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.environment = patch.dict(os.environ, {
            "APP_ENV": "test",
            "ENABLE_STRIPE_WRITES": "false",
            "STRIPE_EXPECT_LIVEMODE": "false",
            "STRIPE_WEBHOOK_SECRET": "whsec_for_unit_tests_only",
            "FINANCE_WEBHOOK_ACCOUNT_ID": "acct_CITest123",
            "FINANCE_WEBHOOK_TENANT_ID": "core8",
        })
        self.environment.start()
    def tearDown(self):
        self.environment.stop()
    def signed(self, content, stamp=None):
        stamp = stamp if stamp is not None else int(time.time())
        secret = os.environ["STRIPE_WEBHOOK_SECRET"]
        digest=hmac.new(secret.encode(),str(stamp).encode()+b'.'+content,hashlib.sha256).hexdigest()
        return {"Stripe-Signature":f"t={stamp},v1={digest}"}
    def payload(self, live=False):
        return json.dumps({"id":"evt_1","type":"invoice.paid","livemode":live,
                           "created":1795340000,"data":{"object":{"id":"in_1"}}}).encode()
    def test_unauthenticated_finance_denied(self):
        self.assertEqual(self.client.get("/finance/overview").status_code,503)
    def test_finance_endpoint_denies_untrusted_tenant_and_role_headers(self):
        for headers in (
            {"X-Tenant-ID": "tenant_alpha", "X-Role": "operator"},
            {"Authorization": "Bearer fake_unsigned_token",
             "X-Tenant-ID": "tenant_alpha", "X-Role": "operator"},
            {"X-User-ID": "user_123", "X-Tenant-ID": "core8",
             "X-Is-Admin": "true"},
        ):
            with self.subTest(headers=headers):
                response = self.client.get("/finance/overview", headers=headers)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("customer", response.text.lower())

    def test_health_fail_closed_when_live_enabled(self):
        with patch.dict(os.environ, {"ENABLE_STRIPE_WRITES":"true"}):
            with self.assertRaises(RuntimeError):
                self.client.get("/health")
    def test_unsigned_webhook_denied(self):
        self.assertEqual(self.client.post("/webhooks/stripe",content=self.payload()).status_code,400)
    def test_oversized_webhook_denied(self):
        data=b"x"*256001
        self.assertEqual(self.client.post("/webhooks/stripe",content=data).status_code,413)
    def test_missing_database_is_retryable(self):
        with patch("main.persist_event", side_effect=RuntimeError("db unavailable")):
            response=self.client.post("/webhooks/stripe",content=self.payload(),
                                      headers=self.signed(self.payload()))
        self.assertEqual(response.status_code,503)
    def test_duplicate_event_receipt(self):
        payload=self.payload()
        with patch("main.persist_event", return_value=False) as save:
            response=self.client.post("/webhooks/stripe",content=payload,headers=self.signed(payload))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["duplicate"], True)
        save.assert_called_once()
    def test_live_webhook_denied(self):
        data=self.payload(live=True)
        response=self.client.post("/webhooks/stripe",content=data,headers=self.signed(data))
        self.assertEqual(response.status_code,400)
if __name__ == "__main__": unittest.main()
