import json
import unittest
from fastapi.testclient import TestClient
from fastapi_fixture import create_test_app, _SECRET
from webhook_signature_demo import signature

NOW=1700000000

class FastApiFixtureTests(unittest.TestCase):
    def setUp(self):
        self.app=create_test_app(now=NOW)
        self.client=TestClient(self.app)
    def tearDown(self):
        self.client.close()
        self.app.state.fixture_db.close()
    def send(self, delivery="D1", payload=None, *, key=_SECRET,
             timestamp=NOW, signature_override=None, credential="demo"):
        if payload is None:
            payload={"submission_id":"S1","name":"Synthetic Contact","consent":True}
        raw=json.dumps(payload).encode()
        headers={
            "x-demo-timestamp":str(timestamp),
            "x-demo-signature":signature_override if signature_override is not None
                               else signature(key,timestamp,raw,delivery_id=delivery),
            "x-demo-delivery-id":delivery,
            "x-demo-credential-id":credential,
        }
        return self.client.post("/offline-fixture/intake",content=raw,headers=headers)
    def test_valid_signed_http_request(self):
        response=self.send()
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()["ok"])
    def test_replayed_delivery_returns_conflict(self):
        self.assertEqual(self.send().status_code,200)
        self.assertEqual(self.send().status_code,409)
    def test_wrong_signature_rejected(self):
        self.assertEqual(self.send(key=b"wrong") .status_code,401)
    def test_unknown_credential_rejected(self):
        self.assertEqual(self.send(credential="unknown").status_code,401)
    def test_expired_signature_rejected(self):
        self.assertEqual(self.send(timestamp=NOW-301).status_code,401)
    def test_missing_consent_rejected(self):
        self.assertEqual(self.send(payload={"submission_id":"S1","name":"Synthetic","consent":False}).status_code,400)
    def test_duplicate_submission_different_delivery_reuses_lead(self):
        self.assertEqual(self.send().status_code,200)
        response=self.send(delivery="D2")
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()["replayed_lead"])
    def test_duplicate_submission_changed_payload_conflicts(self):
        self.send()
        response=self.send(delivery="D2",payload={"submission_id":"S1","name":"Changed","consent":True})
        self.assertEqual(response.status_code,409)
    def test_large_request_rejected_before_signature_verification(self):
        response=self.client.post("/offline-fixture/intake",content=b"x"*65537,
                                  headers={"x-demo-timestamp":str(NOW),
                                           "x-demo-delivery-id":"D-large",
                                           "x-demo-credential-id":"demo"})
        self.assertEqual(response.status_code,413)
    def test_missing_signature_rejected(self):
        response=self.client.post("/offline-fixture/intake",content=b"{}",
                                  headers={"x-demo-timestamp":str(NOW),
                                           "x-demo-delivery-id":"D-missing",
                                           "x-demo-credential-id":"demo"})
        self.assertEqual(response.status_code,401)
    def test_delivery_header_tamper_rejected_over_http(self):
        payload={"submission_id":"S1","name":"Synthetic Contact","consent":True}
        raw=json.dumps(payload).encode()
        response=self.send(delivery="D2",payload=payload,
                           signature_override=signature(_SECRET,NOW,raw,delivery_id="D1"))
        self.assertEqual(response.status_code,401)
        self.assertEqual(self.app.state.fixture_db.execute("SELECT COUNT(*) FROM demo_receipts").fetchone()[0],0)
    def test_legacy_signature_rejected_over_http(self):
        payload={"submission_id":"S1","name":"Synthetic Contact","consent":True}
        raw=json.dumps(payload).encode()
        response=self.send(payload=payload,signature_override=signature(_SECRET,NOW,raw))
        self.assertEqual(response.status_code,401)
    def test_duplicate_security_header_rejected(self):
        response=self.client.post("/offline-fixture/intake",content=b"{}",
            headers=[("x-demo-timestamp",str(NOW)),("x-demo-timestamp",str(NOW))])
        self.assertEqual(response.status_code,400)
        self.assertEqual(response.json()["detail"],"duplicate_header")
        self.assertEqual(self.app.state.fixture_db.execute("SELECT COUNT(*) FROM demo_receipts").fetchone()[0],0)
    def test_content_length_mismatch_rejected(self):
        response=self.client.post("/offline-fixture/intake",content=b"{}",
            headers={"x-demo-timestamp":str(NOW),"content-length":"1"})
        self.assertEqual(response.status_code,400)
        self.assertEqual(response.json()["detail"],"content_length_mismatch")
    def test_noncanonical_timestamp_rejected(self):
        for timestamp in ("+1700000000", "1_700_000_000", "9"*13, " 1700000000"):
            with self.subTest(timestamp=timestamp):
                response=self.client.post("/offline-fixture/intake",content=b"{}",
                    headers={"x-demo-timestamp":timestamp})
                self.assertEqual(response.status_code,400)
                self.assertEqual(response.json()["detail"],"invalid_timestamp")
        self.assertEqual(self.app.state.fixture_db.execute("SELECT COUNT(*) FROM demo_receipts").fetchone()[0],0)
    def test_invalid_timestamp_rejected(self):
        raw=json.dumps({"submission_id":"S1","name":"Synthetic","consent":True}).encode()
        response=self.client.post("/offline-fixture/intake",content=raw,
                                  headers={"x-demo-timestamp":"not-a-time",
                                           "x-demo-delivery-id":"D1",
                                           "x-demo-credential-id":"demo"})
        self.assertEqual(response.status_code,400)

if __name__=="__main__":
    unittest.main()
