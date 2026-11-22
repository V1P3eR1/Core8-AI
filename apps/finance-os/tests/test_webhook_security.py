import hashlib
import hmac
import json
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webhook_security import verify_stripe_event, InvalidWebhook, MAX_PAYLOAD_BYTES

SECRET = 'whsec_test_secret_123'
NOW = 1795340000

def signed(payload, timestamp=NOW, secret=SECRET):
    signature = hmac.new(secret.encode(), str(timestamp).encode() + b'.' + payload, hashlib.sha256).hexdigest()
    return f't={timestamp},v1={signature}'

class StripeWebhookSecurityTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.dumps({'id':'evt_1','type':'invoice.paid','livemode':False}).encode()
    def test_valid_signature(self):
        self.assertEqual('evt_1', verify_stripe_event(self.payload, signed(self.payload), SECRET, now=lambda:NOW)['id'])
    def test_bad_signature_fails(self):
        with self.assertRaises(InvalidWebhook):
            verify_stripe_event(self.payload, signed(self.payload,secret='whsec_anothersecret'),SECRET,now=lambda:NOW)
    def test_mutation_fails(self):
        with self.assertRaises(InvalidWebhook):
            verify_stripe_event(self.payload+b' ',signed(self.payload),SECRET,now=lambda:NOW)
    def test_stale_timestamp_fails(self):
        with self.assertRaises(InvalidWebhook):
            verify_stripe_event(self.payload,signed(self.payload,timestamp=NOW-301),SECRET,now=lambda:NOW)
    def test_future_timestamp_fails(self):
        with self.assertRaises(InvalidWebhook):
            verify_stripe_event(self.payload,signed(self.payload,timestamp=NOW+301),SECRET,now=lambda:NOW)
    def test_live_event_rejected_after_valid_signature(self):
        live = json.dumps({'livemode':True}).encode()
        with self.assertRaises(InvalidWebhook):
            verify_stripe_event(live,signed(live),SECRET,now=lambda:NOW)
    def test_unsigned_rejected(self):
        with self.assertRaises(InvalidWebhook):
            verify_stripe_event(self.payload,'',SECRET,now=lambda:NOW)
    def test_large_payload_rejected(self):
        big = b'a'*(MAX_PAYLOAD_BYTES+1)
        with self.assertRaises(InvalidWebhook):
            verify_stripe_event(big,signed(big),SECRET,now=lambda:NOW)
    def test_invalid_json_rejected(self):
        invalid=b'{broken'
        with self.assertRaises(InvalidWebhook):
            verify_stripe_event(invalid,signed(invalid),SECRET,now=lambda:NOW)
    def test_missing_secret_fails(self):
        with self.assertRaises(InvalidWebhook):
            verify_stripe_event(self.payload,signed(self.payload),'',now=lambda:NOW)

if __name__ == '__main__': unittest.main()
