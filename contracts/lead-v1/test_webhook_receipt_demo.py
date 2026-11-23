import json
import sqlite3
import unittest
from webhook_receipt_demo import receive_once, setup_receipts
from sqlite_atomic_ingest_demo import setup
from webhook_signature_demo import signature

NOW=1700000000
SECRET=b"synthetic-secret"
REGISTRY={"key":{"active":True,"tenant_id":"tenant-A","source_system":"form","secret":SECRET}}

def make_body(submission="S1",name="Synthetic",consent=True):
    return json.dumps({"submission_id":submission,"name":name,"consent":consent}).encode()

class WebhookReceiptTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        setup(self.db)
        setup_receipts(self.db)
    def tearDown(self):
        self.db.close()
    def receive(self,delivery="D1",raw=None,**kwargs):
        raw=make_body() if raw is None else raw
        args=dict(conn=self.db,delivery_id=delivery,raw_body=raw,timestamp=NOW,
                  signature_hex=signature(SECRET,NOW,raw),credential_id="key",
                  credential_registry=REGISTRY,now=NOW,lead_id="L1")
        args.update(kwargs)
        return receive_once(**args)
    def counts(self):
        return tuple(self.db.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
                     for table in ("demo_leads","demo_claims","demo_receipts"))
    def test_valid_delivery_creates_atomic_receipt_and_lead(self):
        self.assertTrue(self.receive()["ok"])
        self.assertEqual(self.counts(),(1,1,1))
    def test_exact_delivery_replay_rejected(self):
        self.receive()
        self.assertEqual(self.receive()["reason"],"delivery_replayed")
        self.assertEqual(self.counts(),(1,1,1))
    def test_new_delivery_same_submission_returns_original(self):
        self.receive()
        r=self.receive(delivery="D2",lead_id="L2")
        self.assertTrue(r["ok"])
        self.assertTrue(r["replayed_lead"])
        self.assertEqual(r["lead_id"],"L1")
        self.assertEqual(self.counts(),(1,1,2))
    def test_new_delivery_changed_submission_payload_conflicts(self):
        self.receive()
        self.assertEqual(self.receive(delivery="D2",raw=make_body(name="Changed"),
                                      lead_id="L2")["reason"],"payload_conflict")
        self.assertEqual(self.counts(),(1,1,1))
    def test_invalid_signature_does_not_consume_receipt(self):
        self.assertEqual(self.receive(signature_hex="0"*64)["reason"],"signature_mismatch")
        self.assertEqual(self.counts(),(0,0,0))
        self.assertTrue(self.receive()["ok"])
    def test_expired_delivery_does_not_consume_receipt(self):
        self.assertEqual(self.receive(now=NOW+301)["reason"],"outside_replay_window")
        self.assertEqual(self.counts(),(0,0,0))
    def test_no_consent_does_not_consume_receipt(self):
        self.assertEqual(self.receive(raw=make_body(consent=False))["reason"],"consent_required")
        self.assertEqual(self.counts(),(0,0,0))
    def test_invalid_delivery_id_denied(self):
        self.assertEqual(self.receive(delivery="")["reason"],"invalid_delivery_id")
        self.assertEqual(self.counts(),(0,0,0))
    def test_claimed_tenant_does_not_change_receipt_tenant(self):
        raw=json.dumps({"submission_id":"S1","name":"Synthetic","consent":True,
                        "tenant_id":"other"}).encode()
        self.assertTrue(self.receive(raw=raw)["ok"])
        self.assertEqual(self.db.execute("SELECT tenant_id FROM demo_receipts").fetchone()[0],"tenant-A")

if __name__=="__main__":
    unittest.main()
