"""Standalone unit tests: python -m unittest discover -s apps/finance-os/tests -v."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from event_policy import parse_event

def event(**overrides):
    value = {
        "id": "evt_1", "type": "invoice.paid", "livemode": False,
        "created": 1795340000,
        "data": {"object": {"id": "in_1", "customer_email": "private@example.com"}}
    }
    value.update(overrides)
    return value

class EventPolicyTests(unittest.TestCase):
    def test_no_private_customer_data_retained(self):
        record = parse_event(event())
        self.assertEqual(record.source_object_id, "in_1")
        self.assertNotIn("private@example.com", repr(record))
    def test_production_rejected(self):
        for live in [True, None, "false"]:
            with self.subTest(live=live), self.assertRaises(ValueError):
                parse_event(event(livemode=live))
    def test_unsupported_ignored(self):
        self.assertIsNone(parse_event(event(type="account.updated")))
    def test_invalid_source_rejected(self):
        with self.assertRaises(ValueError):
            parse_event(event(data={"object": {}}))
    def test_invalid_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            parse_event(event(created="bad"))

if __name__ == "__main__":
    unittest.main()
