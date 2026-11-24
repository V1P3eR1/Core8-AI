import importlib.util
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location("sig",Path(__file__).with_name("webhook_signature_demo.py"))
sig=importlib.util.module_from_spec(spec)
spec.loader.exec_module(sig)
SECRET=b"synthetic-demo-secret-not-for-production"
BODY=b'{"form":"contact","synthetic":true}'
NOW=1700000000

class WebhookSignatureTests(unittest.TestCase):
    def signed(self, timestamp=NOW, body=BODY):
        return sig.signature(SECRET,timestamp,body)
    def test_valid_signature(self):
        self.assertTrue(sig.verify(SECRET,NOW,BODY,self.signed(),now=NOW)["ok"])
    def test_tampered_body_denied(self):
        self.assertEqual(sig.verify(SECRET,NOW,BODY+b"!",self.signed(),now=NOW)["reason"],"signature_mismatch")
    def test_wrong_secret_denied(self):
        self.assertEqual(sig.verify(b"other",NOW,BODY,self.signed(),now=NOW)["reason"],"signature_mismatch")
    def test_old_message_denied(self):
        self.assertEqual(sig.verify(SECRET,NOW-301,BODY,self.signed(NOW-301),now=NOW)["reason"],"outside_replay_window")
    def test_future_message_denied(self):
        self.assertEqual(sig.verify(SECRET,NOW+31,BODY,self.signed(NOW+31),now=NOW)["reason"],"outside_replay_window")
    def test_within_window_allowed(self):
        self.assertTrue(sig.verify(SECRET,NOW-300,BODY,self.signed(NOW-300),now=NOW)["ok"])
    def test_invalid_signature_denied(self):
        self.assertEqual(sig.verify(SECRET,NOW,BODY,"not-hex",now=NOW)["reason"],"invalid_signature")
    def test_non_ascii_signature_denied(self):
        self.assertEqual(sig.verify(SECRET,NOW,BODY,chr(233)*64,now=NOW)["reason"],"invalid_signature")
    def test_oversized_body_denied(self):
        self.assertEqual(sig.verify(SECRET,NOW,b"x"*65537,self.signed(),now=NOW)["reason"],"invalid_body")
    def test_invalid_timestamp_denied(self):
        self.assertEqual(sig.verify(SECRET,True,BODY,self.signed(),now=NOW)["reason"],"invalid_timestamp")
    def test_missing_secret_denied(self):
        self.assertEqual(sig.verify(b"",NOW,BODY,self.signed(),now=NOW)["reason"],"invalid_secret")

if __name__=="__main__":
    unittest.main()
