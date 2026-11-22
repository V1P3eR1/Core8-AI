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


    def test_real_postgres_savepoint_retry_and_dead_letter(self):
        """A real PostgreSQL trigger fails one event while another succeeds."""
        from worker import process_batch
        marker = uuid4().hex
        bad_id, good_id = "evt_fail_" + marker, "evt_good_" + marker
        bad_obj, good_obj = "ci_fail_" + marker, "ci_good_" + marker
        trigger_name = "finance_ci_reject_activity"
        function_name = "finance_ci_reject_activity"
        original = {key: os.environ.get(key) for key in ("APP_ENV", "ENABLE_STRIPE_WRITES")}
        os.environ.update({"APP_ENV": "test", "ENABLE_STRIPE_WRITES": "false"})
        # Test-owned trigger only on the disposable CI database. No production writes.
        with psycopg.connect(os.environ["DATABASE_URL"]) as db:
            db.execute("""
                CREATE OR REPLACE FUNCTION finance_ci_reject_activity()
                RETURNS trigger LANGUAGE plpgsql AS $
                BEGIN
                  IF NEW.source_object_id LIKE 'ci_fail_%' THEN
                    RAISE EXCEPTION 'injected retry test failure';
                  END IF;
                  RETURN NEW;
                END $;
            """)
            db.execute("""
                CREATE TRIGGER finance_ci_reject_activity
                BEFORE INSERT ON finance_activity
                FOR EACH ROW EXECUTE FUNCTION finance_ci_reject_activity()
            """)
            for eid, obj in ((bad_id, bad_obj), (good_id, good_obj)):
                db.execute("""
                    INSERT INTO finance_stripe_event_inbox
                      (event_id, organization_id, event_type, source_object_id, event_created)
                    VALUES (%s, 'core8', 'invoice.paid', %s, now())
                """, (eid, obj))
        try:
            processed = process_batch()
            self.assertGreaterEqual(processed, 1)
            with psycopg.connect(os.environ["DATABASE_URL"]) as db:
                result = db.execute("""
                    SELECT event_id, status, attempts, next_attempt_at
                    FROM finance_stripe_event_inbox WHERE event_id IN (%s, %s)
                """, (bad_id, good_id)).fetchall()
                states = {eid: (status, attempts, next_retry)
                          for eid, status, attempts, next_retry in result}
                self.assertEqual(states[good_id][:2], ("processed", 0))
                self.assertEqual(states[bad_id][:2], ("failed", 1))
                self.assertIsNotNone(states[bad_id][2])
                activity_count = db.execute("""
                    SELECT count(*) FROM finance_activity
                    WHERE stripe_event_id IN (%s, %s)
                """, (bad_id, good_id)).fetchone()[0]
                self.assertEqual(activity_count, 1)
                # Force the remaining retry to become due at the last attempt.
                db.execute("""
                    UPDATE finance_stripe_event_inbox
                    SET attempts=4, next_attempt_at=now()-interval '1 second'
                    WHERE event_id=%s
                """, (bad_id,))
            process_batch()
            with psycopg.connect(os.environ["DATABASE_URL"]) as db:
                status, attempts, next_retry = db.execute("""
                    SELECT status, attempts, next_attempt_at
                    FROM finance_stripe_event_inbox WHERE event_id=%s
                """, (bad_id,)).fetchone()
                self.assertEqual((status, attempts, next_retry), ("dead", 5, None))
                self.assertEqual(db.execute("""
                    SELECT count(*) FROM finance_activity WHERE stripe_event_id=%s
                """, (bad_id,)).fetchone()[0], 0)
        finally:
            with psycopg.connect(os.environ["DATABASE_URL"]) as db:
                db.execute("DROP TRIGGER IF EXISTS finance_ci_reject_activity ON finance_activity")
                db.execute("DROP FUNCTION IF EXISTS finance_ci_reject_activity()")
                db.execute("DELETE FROM finance_activity WHERE stripe_event_id IN (%s,%s)",
                           (bad_id, good_id))
                db.execute("DELETE FROM finance_stripe_event_inbox WHERE event_id IN (%s,%s)",
                           (bad_id, good_id))
            for key, val in original.items():
                if val is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = val


if __name__=="__main__": unittest.main()
