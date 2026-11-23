import json
import sqlite3
import unittest
from webhook_receipt_demo import receive_once, setup_receipts
from sqlite_atomic_ingest_demo import setup
from webhook_signature_demo import signature

NOW=1700000000
NEW=b"synthetic-new"
OLD=b"synthetic-old"
BODY=json.dumps({"submission_id":"S1","name":"Synthetic","consent":True}).encode()

class RotatingReceiptTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        setup(self.db)
        setup_receipts(self.db)
        self.registry={"key":{"active":True,"tenant_id":"tenant-A",
                              "source_system":"form","secret":NEW,
                              "previous_secret":OLD,
                              "previous_valid_until":NOW+60}}
    def tearDown(self):
        self.db.close()
    def receive(self,key,delivery="D1",now=NOW):
        return receive_once(
            self.db,delivery_id=delivery,raw_body=BODY,timestamp=NOW,
            signature_hex=signature(key,NOW,BODY),credential_id="key",
            credential_registry=self.registry,now=now,lead_id="L1")
    def test_previous_key_creates_lead_during_grace(self):
        self.assertTrue(self.receive(OLD)["ok"])
    def test_new_key_creates_lead(self):
        self.assertTrue(self.receive(NEW)["ok"])
    def test_previous_key_rejected_after_grace_without_receipt(self):
        self.assertEqual(self.receive(OLD,now=NOW+61)["reason"],"signature_mismatch")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM demo_receipts").fetchone()[0],0)
    def test_new_key_accepted_after_previous_expires(self):
        self.assertTrue(self.receive(NEW,now=NOW+61)["ok"])
    def test_previous_and_new_signatures_cannot_replay_same_delivery(self):
        self.assertTrue(self.receive(OLD)["ok"])
        self.assertEqual(self.receive(NEW)["reason"],"delivery_replayed")
    def test_invalid_signature_cannot_consume_delivery(self):
        self.assertEqual(self.receive(b"unknown")["reason"],"signature_mismatch")
        self.assertTrue(self.receive(NEW)["ok"])

if __name__=="__main__":
    unittest.main()
