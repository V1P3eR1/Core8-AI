import importlib.util
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location("atomic",Path(__file__).with_name("sqlite_atomic_ingest_demo.py"))
atomic=importlib.util.module_from_spec(spec)
spec.loader.exec_module(atomic)

def params(lead_id="L1",tenant="A",digest="a"*64):
    return dict(trusted_tenant_id=tenant,source_system="lead_triage",
                submission_id="submission-1",lead_id=lead_id,
                payload_sha256=digest,name="Fictional Customer")

class AtomicIngestTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(":memory:")
        atomic.setup(self.conn)
    def tearDown(self):
        self.conn.close()
    def test_replay_is_same_lead(self):
        self.assertFalse(atomic.ingest(self.conn,**params())["replayed"])
        r=atomic.ingest(self.conn,**params("L2"))
        self.assertTrue(r["replayed"])
        self.assertEqual(r["lead_id"],"L1")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM demo_leads").fetchone()[0],1)
    def test_conflicting_payload_rejected_without_new_lead(self):
        atomic.ingest(self.conn,**params())
        self.assertEqual(atomic.ingest(self.conn,**params("L2",digest="b"*64)),
                         {"ok":False,"conflict":True})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM demo_leads").fetchone()[0],1)
    def test_rollback_and_retry(self):
        with self.assertRaises(RuntimeError):
            atomic.ingest(self.conn,**params(),fail_after_lead=True)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM demo_leads").fetchone()[0],0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM demo_claims").fetchone()[0],0)
        self.assertTrue(atomic.ingest(self.conn,**params())["ok"])
    def test_cross_tenant_is_independent(self):
        atomic.ingest(self.conn,**params())
        atomic.ingest(self.conn,**params("L2",tenant="B"))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM demo_leads").fetchone()[0],2)
    def test_parallel_claim_and_lead_atomicity(self):
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/"test.sqlite")
            c=sqlite3.connect(path);atomic.setup(c);c.close()
            barrier=threading.Barrier(4);results=[];errors=[];lock=threading.Lock()
            def worker(i):
                connection=sqlite3.connect(path,timeout=10)
                try:
                    barrier.wait(timeout=5)
                    r=atomic.ingest(connection,**params(f"L{i}"))
                    with lock:results.append(r)
                except Exception as e:
                    with lock:errors.append(str(e))
                finally:connection.close()
            threads=[threading.Thread(target=worker,args=(i,)) for i in range(4)]
            for t in threads:t.start()
            for t in threads:t.join(timeout=15)
            self.assertEqual(errors,[])
            self.assertEqual(len(results),4)
            self.assertEqual(len({r["lead_id"] for r in results}),1)
            c=sqlite3.connect(path)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM demo_leads").fetchone()[0],1)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM demo_claims").fetchone()[0],1)
            c.close()

if __name__=="__main__":
    unittest.main()
