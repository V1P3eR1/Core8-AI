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
                  signature_hex=signature(SECRET,NOW,raw,delivery_id=delivery) if delivery and delivery.isascii() and delivery.isprintable() else "0"*64,credential_id="key",
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
    def test_delivery_header_tampering_rejected(self):
        raw=make_body()
        signed_for_d1=signature(SECRET,NOW,raw,delivery_id="D1")
        self.assertEqual(self.receive(delivery="D2",signature_hex=signed_for_d1)["reason"],"signature_mismatch")
        self.assertEqual(self.counts(),(0,0,0))
    def test_legacy_unbound_signature_rejected(self):
        raw=make_body()
        self.assertEqual(self.receive(signature_hex=signature(SECRET,NOW,raw))["reason"],"signature_mismatch")
        self.assertEqual(self.counts(),(0,0,0))
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
        self.assertEqual(self.receive(delivery="",signature_hex="0"*64)["reason"],"invalid_delivery_id")
        self.assertEqual(self.counts(),(0,0,0))
    def test_non_ascii_delivery_id_denied_before_signature(self):
        self.assertEqual(self.receive(delivery="D-\u2603",signature_hex="0"*64)["reason"],"invalid_delivery_id")
        self.assertEqual(self.counts(),(0,0,0))
    def test_control_character_delivery_id_denied_before_signature(self):
        self.assertEqual(self.receive(delivery="D-\n",signature_hex="0"*64)["reason"],"invalid_delivery_id")
        self.assertEqual(self.counts(),(0,0,0))
    def test_identical_delivery_and_submission_are_isolated_by_tenant(self):
        other_secret=b"synthetic-other-secret"
        registry={**REGISTRY,"other":{"active":True,"tenant_id":"tenant-B",
                                     "source_system":"form","secret":other_secret}}
        self.assertTrue(self.receive(credential_registry=registry)["ok"])
        raw=make_body(name="Other Synthetic")
        signed=signature(other_secret,NOW,raw,delivery_id="D1")
        self.assertEqual(self.receive(raw=raw,credential_id="other",
            credential_registry=registry)["reason"],"signature_mismatch")
        self.assertEqual(self.counts(),(1,1,1))
        result=self.receive(raw=raw,credential_id="other",
            credential_registry=registry,signature_hex=signed)
        self.assertTrue(result["ok"])
        self.assertFalse(result["replayed_lead"])
        self.assertEqual(self.counts(),(2,2,2))
        self.assertEqual(self.db.execute(
            "SELECT tenant_id,name FROM demo_leads ORDER BY tenant_id").fetchall(),
            [("tenant-A","Synthetic"),("tenant-B","Other Synthetic")])
        self.assertEqual(self.receive(raw=raw,credential_id="other",
            credential_registry=registry,signature_hex=signed)["reason"],"delivery_replayed")
        self.assertEqual(self.counts(),(2,2,2))
    def test_same_tenant_different_sources_have_independent_claims(self):
        other_secret=b"synthetic-source-secret"
        registry={**REGISTRY,"second":{"active":True,"tenant_id":"tenant-A",
                                       "source_system":"second-form","secret":other_secret}}
        self.assertTrue(self.receive(credential_registry=registry)["ok"])
        raw=make_body(name="Second Source")
        signed=signature(other_secret,NOW,raw,delivery_id="D1")
        result=self.receive(raw=raw,credential_id="second",credential_registry=registry,
                            signature_hex=signed,lead_id="L2")
        self.assertTrue(result["ok"])
        self.assertFalse(result["replayed_lead"])
        self.assertEqual(self.counts(),(2,2,2))
        self.assertEqual(self.db.execute(
            "SELECT source_system,lead_id FROM demo_claims ORDER BY source_system").fetchall(),
            [("form","L1"),("second-form","L2")])
        self.assertEqual(self.receive(credential_registry=registry)["reason"],"delivery_replayed")
        self.assertEqual(self.counts(),(2,2,2))
    def test_receipt_write_failure_rolls_back_lead_and_allows_retry(self):
        self.db.execute("""CREATE TRIGGER reject_receipt BEFORE INSERT ON demo_receipts
            BEGIN SELECT RAISE(ABORT, 'injected receipt failure'); END""")
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.receive()
        self.assertEqual(self.counts(),(0,0,0))
        self.assertFalse(self.db.in_transaction)
        self.db.execute("DROP TRIGGER reject_receipt")
        self.db.commit()
        self.assertTrue(self.receive()["ok"])
        self.assertEqual(self.counts(),(1,1,1))
        self.assertEqual(self.receive()["reason"],"delivery_replayed")
    def test_claimed_tenant_does_not_change_receipt_tenant(self):
        raw=json.dumps({"submission_id":"S1","name":"Synthetic","consent":True,
                        "tenant_id":"other"}).encode()
        self.assertTrue(self.receive(raw=raw)["ok"])
        self.assertEqual(self.db.execute("SELECT tenant_id FROM demo_receipts").fetchone()[0],"tenant-A")

if __name__=="__main__":
    unittest.main()
