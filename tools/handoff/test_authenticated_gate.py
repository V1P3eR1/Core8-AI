import hashlib
import hmac
import json
import unittest
from datetime import datetime, timezone

from authenticated_gate import (DOMAIN, bind_signed_review_evidence,
                                verify_gate_receipt)
from github_provenance import EvidenceBlocked, REPO

NOW = datetime(2026, 11, 23, 10, 30, tzinfo=timezone.utc)
KEY = b"K" * 32


class AuthenticatedGateTests(unittest.TestCase):
    def setUp(self):
        self.approval = {"repo": REPO, "issue_number": 62, "comment_id": 456,
                         "approver_id": 999, "task_uuid": "11111111-2222-4333-8444-555555555555",
                         "task_digest": "a"*64, "issue_body_sha256": "b"*64,
                         "comment_created_at": "2026-11-23T08:05:00Z"}
        self.run = {"repo": REPO, "run_id": 123, "artifact_id": 789,
                    "approver_id": 999, "head_sha": "c"*40,
                    "run_conclusion": "success", "run_event": "issue_comment",
                    "expired": False, "archive_sha256": "d"*64,
                    "created_at": "2026-11-23T08:10:00Z",
                    "expires_at": "2026-11-30T08:10:00Z"}
        self.gate = {key: val for key, val in self.approval.items()
                     if key != "comment_created_at"}
        self.gate.update(run_id=123, artifact_id=789, head_sha="c"*40,
                         task_revision=1, approved_at="2026-11-23T08:00:00Z")

    def envelope(self, record=None, key=KEY):
        raw = json.dumps(self.gate if record is None else record, sort_keys=True,
                         ensure_ascii=False, separators=(",", ":")).encode()
        sig = hmac.new(key, DOMAIN + raw, hashlib.sha256).hexdigest()
        return raw, sig

    def test_valid_signature_still_review_only(self):
        raw, sig = self.envelope()
        value = bind_signed_review_evidence(self.approval, self.run, raw, sig,
                                            verifier_key=KEY, now=NOW)
        self.assertEqual(value["status"], "BOUND_FOR_REVIEW_ONLY")
        self.assertNotIn("publish_authorized", value)

    def test_modified_signed_record_rejected(self):
        raw, sig = self.envelope()
        with self.assertRaisesRegex(EvidenceBlocked, "gate_signature_mismatch"):
            verify_gate_receipt(raw.replace(b'"comment_id":456', b'"comment_id":457'),
                                sig, verifier_key=KEY)

    def test_key_rotation_blocks_old_signature(self):
        raw, sig = self.envelope()
        with self.assertRaisesRegex(EvidenceBlocked, "gate_signature_mismatch"):
            verify_gate_receipt(raw, sig, verifier_key=b"Z"*32)

    def test_signature_of_unexpected_schema_rejected_by_binding(self):
        record = dict(self.gate, bypass=True)
        raw, sig = self.envelope(record)
        with self.assertRaisesRegex(EvidenceBlocked, "invalid_gate_schema"):
            bind_signed_review_evidence(self.approval, self.run, raw, sig,
                                        verifier_key=KEY, now=NOW)

    def test_short_verifier_key_rejected(self):
        raw, sig = self.envelope()
        with self.assertRaisesRegex(EvidenceBlocked, "missing_protected_gate_key"):
            verify_gate_receipt(raw, sig, verifier_key=b"short")

    def test_duplicate_keys_rejected_even_when_signed(self):
        raw = b'{"repo":"a","repo":"b"}'
        sig = hmac.new(KEY, DOMAIN + raw, hashlib.sha256).hexdigest()
        with self.assertRaisesRegex(EvidenceBlocked, "gate_duplicate_json_key"):
            verify_gate_receipt(raw, sig, verifier_key=KEY)

    def test_signed_noncanonical_json_rejected(self):
        raw = b'{ "repo":"a" }'
        sig = hmac.new(KEY, DOMAIN + raw, hashlib.sha256).hexdigest()
        with self.assertRaisesRegex(EvidenceBlocked, "noncanonical_signed_gate_json"):
            verify_gate_receipt(raw, sig, verifier_key=KEY)

    def test_oversized_payload_rejected(self):
        raw = b"x" * 8193
        sig = hmac.new(KEY, DOMAIN + raw, hashlib.sha256).hexdigest()
        with self.assertRaisesRegex(EvidenceBlocked, "invalid_signed_gate_bytes"):
            verify_gate_receipt(raw, sig, verifier_key=KEY)

    def test_invalid_utf8_rejected(self):
        raw = b"\xff"
        sig = hmac.new(KEY, DOMAIN + raw, hashlib.sha256).hexdigest()
        with self.assertRaisesRegex(EvidenceBlocked, "invalid_signed_gate_json"):
            verify_gate_receipt(raw, sig, verifier_key=KEY)

    def test_wrong_comment_fails_after_signature(self):
        raw, sig = self.envelope()
        self.approval["comment_id"] = 100
        with self.assertRaisesRegex(EvidenceBlocked, "approval_gate_mismatch"):
            bind_signed_review_evidence(self.approval, self.run, raw, sig,
                                        verifier_key=KEY, now=NOW)

    def test_missing_signature_fails_closed(self):
        raw, _ = self.envelope()
        with self.assertRaises(EvidenceBlocked):
            verify_gate_receipt(raw, None, verifier_key=KEY)

    def test_missing_protected_gate_fails_closed(self):
        raw, sig = self.envelope()
        with self.assertRaises(EvidenceBlocked):
            verify_gate_receipt(None, sig, verifier_key=KEY)


if __name__ == "__main__":
    unittest.main()
