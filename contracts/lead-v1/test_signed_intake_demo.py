import json
import sqlite3
import unittest
from signed_intake_demo import signed_intake
from sqlite_atomic_ingest_demo import setup
from webhook_signature_demo import signature

NOW=1700000000
SECRET=b"synthetic-only-signing-secret"
REGISTRY={"fixture-credential":{"active":True,"tenant_id":"tenant-A",
                                "source_system":"lead_triage","secret":SECRET}}

def body(**updates):
    p={"submission_id":"submission-1","name":"Fictional Contact","consent":True}
    p.update(updates)
    return json.dumps(p,sort_keys=True).encode()

class SignedIntakeTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        setup(self.db)
    def tearDown(self):
        self.db.close()
    def run_intake(self, raw_body=None, **overrides):
        raw=body() if raw_body is None else raw_body
        args=dict(raw_body=raw,timestamp=NOW,signature_hex=signature(SECRET,NOW,raw),
                  credential_id="fixture-credential",credential_registry=REGISTRY,
                  now=NOW,lead_id="L1")
        args.update(overrides)
        return signed_intake(self.db,**args)
    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM demo_leads").fetchone()[0]
    def test_verified_signed_request_creates_lead(self):
        self.assertTrue(self.run_intake()["ok"])
        self.assertEqual(self.count(),1)
    def test_replay_returns_original_lead(self):
        self.run_intake()
        r=self.run_intake(lead_id="L2")
        self.assertTrue(r["replayed"])
        self.assertEqual(r["lead_id"],"L1")
        self.assertEqual(self.count(),1)
    def test_same_submission_different_payload_conflicts(self):
        self.run_intake()
        self.assertTrue(self.run_intake(raw_body=body(name="Different"),lead_id="L2")["conflict"])
        self.assertEqual(self.count(),1)
    def test_tampered_body_denied(self):
        raw=body(name="Tampered")
        self.assertEqual(self.run_intake(raw_body=raw,signature_hex=signature(SECRET,NOW,body()))["reason"],"signature_mismatch")
        self.assertEqual(self.count(),0)
    def test_unknown_credential_denied(self):
        self.assertEqual(self.run_intake(credential_id="unknown")["reason"],"unknown_credential")
    def test_inactive_credential_denied(self):
        registry={"fixture-credential":dict(REGISTRY["fixture-credential"],active=False)}
        self.assertEqual(self.run_intake(credential_registry=registry)["reason"],"unknown_credential")
    def test_expired_timestamp_denied(self):
        self.assertEqual(self.run_intake(now=NOW+301)["reason"],"outside_replay_window")
    def test_missing_consent_denied(self):
        self.assertEqual(self.run_intake(raw_body=body(consent=False))["reason"],"consent_required")
        self.assertEqual(self.count(),0)
    def test_claimed_tenant_is_ignored(self):
        self.run_intake(raw_body=body(tenant_id="attacker-tenant"))
        self.assertEqual(self.db.execute("SELECT tenant_id FROM demo_leads").fetchone()[0],"tenant-A")
    def test_invalid_json_denied(self):
        self.assertEqual(self.run_intake(raw_body=b"{")["reason"],"invalid_json")
    def test_no_unsigned_fallback(self):
        self.assertEqual(self.run_intake(signature_hex="")["reason"],"invalid_signature")
        self.assertEqual(self.count(),0)

if __name__=="__main__":
    unittest.main()
