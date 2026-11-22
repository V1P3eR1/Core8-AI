"""PostgreSQL + HTTP sandbox E2E test: real signature, inbox dedup, worker exactly once."""
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
import unittest
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import psycopg
    from fastapi.testclient import TestClient
    from main import app
    from worker import process_batch
    READY = bool(os.getenv("DATABASE_URL"))
except ImportError:
    READY = False

@unittest.skipUnless(READY, "requires PostgreSQL sandbox DATABASE_URL and psycopg")
class TestPostgresEventFlow(unittest.TestCase):
    def test_signature_ingest_dedup_and_worker(self):
        secret = "whsec_ci_integration_only"
        original = {key:os.environ.get(key) for key in
                    ("APP_ENV","STRIPE_WEBHOOK_SECRET","ENABLE_STRIPE_WRITES","STRIPE_EXPECT_LIVEMODE")}
        os.environ.update({"APP_ENV":"test","STRIPE_WEBHOOK_SECRET":secret,
                           "ENABLE_STRIPE_WRITES":"false","STRIPE_EXPECT_LIVEMODE":"false"})
        eid = "evt_ci_" + uuid4().hex
        payload = json.dumps({
            "id":eid,"livemode":False,"created":int(time.time()),
            "type":"invoice.paid","data":{"object":{"id":"in_ci_123","customer_email":"not-stored@example.org"}}
        }).encode()
        ts = int(time.time())
        digest = hmac.new(secret.encode(),str(ts).encode()+b'.'+payload,hashlib.sha256).hexdigest()
        try:
            client=TestClient(app)
            first=client.post("/webhooks/stripe",content=payload,
                              headers={"Stripe-Signature":f"t={ts},v1={digest}"})
            self.assertEqual(first.status_code,200,first.text)
            self.assertEqual(first.json()["queued"],True)
            second=client.post("/webhooks/stripe",content=payload,
                               headers={"Stripe-Signature":f"t={ts},v1={digest}"})
            self.assertEqual(second.status_code,200,second.text)
            self.assertEqual(second.json()["duplicate"],True)
            with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
                count=connection.execute("SELECT count(*) FROM finance_stripe_event_inbox WHERE event_id=%s",(eid,)).fetchone()[0]
                self.assertEqual(count,1)
            process_batch()
            process_batch()
            with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
                count=connection.execute("SELECT count(*) FROM finance_activity WHERE stripe_event_id=%s",(eid,)).fetchone()[0]
                self.assertEqual(count,1)
                self.assertEqual(connection.execute(
                    "SELECT status FROM finance_stripe_event_inbox WHERE event_id=%s",(eid,)).fetchone()[0],"processed")
                self.assertNotIn("not-stored@example.org",str(connection.execute(
                    "SELECT * FROM finance_stripe_event_inbox WHERE event_id=%s",(eid,)).fetchone()))
        finally:
            for key,val in original.items():
                if val is None: os.environ.pop(key,None)
                else: os.environ[key]=val

if __name__=="__main__": unittest.main()
