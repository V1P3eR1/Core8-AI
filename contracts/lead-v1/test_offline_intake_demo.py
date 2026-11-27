import importlib.util
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parent))
from sqlite_atomic_ingest_demo import setup
from offline_intake_demo import preview_intake

def args():
    return dict(
        identity={"verified":True,"sub":"synthetic-user"},
        memberships=[{"user_id":"synthetic-user","tenant_id":"tenant-A",
                      "active":True,"permissions":["lead:intake"]}],
        requested_tenant_id="tenant-A",source_system="lead_triage",
        submission_id="synthetic-submission-1",lead_id="synthetic-lead-1",
        name="Fictional Contact",
        payload={"consent":True,"source_verified":True,"message":"Synthetic inquiry"}
    )

class OfflineIntakeTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        setup(self.db)
    def tearDown(self):
        self.db.close()
    def run_intake(self,**updates):
        values=args()
        values.update(updates)
        return preview_intake(self.db,**values)
    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM demo_leads").fetchone()[0]
    def test_verified_and_authorized_creates_one_lead(self):
        r=self.run_intake()
        self.assertEqual(r,{"ok":True,"lead_id":"synthetic-lead-1","replayed":False})
        self.assertEqual(self.count(),1)
    def test_same_payload_replays_original_lead(self):
        self.run_intake()
        r=self.run_intake(lead_id="synthetic-lead-2")
        self.assertEqual(r["lead_id"],"synthetic-lead-1")
        self.assertTrue(r["replayed"])
        self.assertEqual(self.count(),1)
    def test_changed_payload_returns_conflict(self):
        self.run_intake()
        r=self.run_intake(lead_id="synthetic-lead-2",
                          payload={"consent":True,"source_verified":True,"message":"Different"})
        self.assertEqual(r,{"ok":False,"conflict":True})
        self.assertEqual(self.count(),1)
    def test_missing_tenant_membership_denied_before_write(self):
        self.assertEqual(self.run_intake(memberships=[])["reason"],"forbidden")
        self.assertEqual(self.count(),0)
    def test_admin_without_membership_denied(self):
        self.assertEqual(self.run_intake(identity={"verified":True,"sub":"synthetic-user","role":"admin"},
                                         requested_tenant_id="tenant-B")["reason"],"forbidden")
        self.assertEqual(self.count(),0)
    def test_unsigned_source_denied_before_write(self):
        self.assertEqual(self.run_intake(payload={"consent":True,"source_verified":False})["reason"],"source_unverified")
        self.assertEqual(self.count(),0)
    def test_missing_consent_denied_before_write(self):
        self.assertEqual(self.run_intake(payload={"consent":False,"source_verified":True})["reason"],"consent_required")
        self.assertEqual(self.count(),0)
    def test_invalid_payload_denied(self):
        self.assertEqual(self.run_intake(payload=None)["reason"],"invalid_payload")
        self.assertEqual(self.count(),0)
    def test_unverified_identity_denied(self):
        self.assertEqual(self.run_intake(identity={"sub":"synthetic-user"})["reason"],"unauthenticated")
        self.assertEqual(self.count(),0)

if __name__=="__main__":
    unittest.main()
