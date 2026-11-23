import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from webhook_receipt_demo import receive_once, setup_receipts
from sqlite_atomic_ingest_demo import setup
from webhook_signature_demo import signature

NOW=1700000000
SECRET=b"synthetic-concurrency-key"
REGISTRY={"key":{"active":True,"tenant_id":"tenant-A","source_system":"form","secret":SECRET}}
BODY=json.dumps({"submission_id":"S1","name":"Synthetic","consent":True}).encode()

class ConcurrentWebhookReceiptTests(unittest.TestCase):
    def test_simultaneous_identical_delivery_is_accepted_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/"webhooks.sqlite")
            conn=sqlite3.connect(path)
            setup(conn)
            setup_receipts(conn)
            conn.close()
            barrier=threading.Barrier(5)
            results=[]
            errors=[]
            lock=threading.Lock()
            def worker(index):
                connection=sqlite3.connect(path,timeout=15)
                try:
                    barrier.wait(timeout=10)
                    result=receive_once(
                        connection,delivery_id="D1",raw_body=BODY,
                        timestamp=NOW,signature_hex=signature(SECRET,NOW,BODY),
                        credential_id="key",credential_registry=REGISTRY,
                        now=NOW,lead_id=f"L{index}")
                    with lock: results.append(result)
                except Exception as exc:
                    with lock: errors.append(repr(exc))
                finally:
                    connection.close()
            threads=[threading.Thread(target=worker,args=(i,)) for i in range(5)]
            for thread in threads: thread.start()
            for thread in threads: thread.join(timeout=20)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(errors,[])
            self.assertEqual(len(results),5)
            self.assertEqual(sum(result.get("ok") is True for result in results),1)
            self.assertEqual(sum(result.get("reason")=="delivery_replayed" for result in results),4)
            conn=sqlite3.connect(path)
            for table in ("demo_leads","demo_claims","demo_receipts"):
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM "+table).fetchone()[0],1)
            conn.close()

    def test_same_delivery_id_is_independent_per_tenant(self):
        conn=sqlite3.connect(":memory:")
        setup(conn)
        setup_receipts(conn)
        try:
            for tenant in ("tenant-A","tenant-B"):
                registry={"key":dict(REGISTRY["key"],tenant_id=tenant)}
                result=receive_once(
                    conn,delivery_id="D1",raw_body=BODY,timestamp=NOW,
                    signature_hex=signature(SECRET,NOW,BODY),credential_id="key",
                    credential_registry=registry,now=NOW,lead_id="L-"+tenant)
                self.assertTrue(result["ok"])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM demo_receipts").fetchone()[0],2)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM demo_leads").fetchone()[0],2)
        finally:
            conn.close()

if __name__=="__main__":
    unittest.main()
