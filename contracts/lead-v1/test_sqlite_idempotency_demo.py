import importlib.util
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "demo", Path(__file__).with_name("sqlite_idempotency_demo.py")
)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)

class SQLiteIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        demo.setup(self.conn)

    def tearDown(self):
        self.conn.close()

    def add(self, **kw):
        d = dict(tenant_id="A", source_system="lead_triage",
                 submission_id="submission-1", lead_id="lead-1",
                 payload_sha256="a" * 64)
        d.update(kw)
        return demo.claim(self.conn, **d)

    def test_replay(self):
        self.assertFalse(self.add()["replayed"])
        self.assertEqual(self.add(lead_id="lead-2")["lead_id"], "lead-1")
        self.assertTrue(self.add(lead_id="lead-2")["replayed"])

    def test_payload_conflict(self):
        self.add()
        self.assertEqual(self.add(lead_id="lead-2", payload_sha256="b"*64),
                         {"ok": False, "conflict": True})

    def test_tenant_isolation(self):
        self.add()
        self.assertEqual(self.add(tenant_id="B", lead_id="lead-2")["lead_id"], "lead-2")

    def test_source_isolation(self):
        self.add()
        self.assertEqual(self.add(source_system="social", lead_id="lead-2")["lead_id"], "lead-2")

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            self.add(tenant_id="")

    def test_parallel_same_key_one_row(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "disposable.sqlite")
            conn = sqlite3.connect(path)
            demo.setup(conn)
            conn.close()
            barrier = threading.Barrier(4)
            results = []
            errors = []
            lock = threading.Lock()
            def worker(n):
                c = sqlite3.connect(path, timeout=10)
                try:
                    barrier.wait(timeout=5)
                    r = demo.claim(c, tenant_id="A", source_system="lead_triage",
                                   submission_id="same", lead_id=f"L{n}",
                                   payload_sha256="c"*64)
                    with lock:
                        results.append(r)
                except Exception as exc:
                    with lock:
                        errors.append(str(exc))
                finally:
                    c.close()
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=15)
            self.assertEqual(errors, [])
            self.assertEqual(len(results), 4)
            self.assertEqual(len({r["lead_id"] for r in results}), 1)
            verify = sqlite3.connect(path)
            self.assertEqual(verify.execute("SELECT COUNT(*) FROM demo_claims").fetchone()[0], 1)
            verify.close()

if __name__ == "__main__":
    unittest.main()
