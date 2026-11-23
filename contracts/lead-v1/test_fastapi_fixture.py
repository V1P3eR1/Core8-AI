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
                               else signature(key,timestamp,raw),
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
    def test_invalid_timestamp_rejected(self):
        raw=json.dumps({"submission_id":"S1","name":"Synthetic","consent":True}).encode()
        response=self.client.post("/offline-fixture/intake",content=raw,
                                  headers={"x-demo-timestamp":"not-a-time",
                                           "x-demo-delivery-id":"D1",
                                           "x-demo-credential-id":"demo"})
        self.assertEqual(response.status_code,400)

if __name__=="__main__":
    unittest.main()
