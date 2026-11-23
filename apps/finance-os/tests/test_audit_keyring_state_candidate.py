"""Synthetic signed audit-keyring snapshot and anti-rollback tests."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_key_rotation_candidate import AuditKeyringCandidate, PinnedAuditKey
from audit_keyring_state_candidate import (
    export_audit_keyring_state, import_audit_keyring_state,
)
from tenant_access import FinanceAccessDenied

MAC = b"synthetic-independent-snapshot-mac-key-over-32bytes"
OLD = PinnedAuditKey("audit_old", b"synthetic-old-32-byte-ci-hmac-key-material")
NEW = PinnedAuditKey("audit_new", b"synthetic-new-32-byte-ci-hmac-key-material")


class AuditKeyringStateCandidateTests(unittest.TestCase):
    def setUp(self):
        self.ring = AuditKeyringCandidate(active=OLD)
        self.old_blob = export_audit_keyring_state(self.ring, signing_key=MAC)

    def recover(self, blob, generation, material, **overrides):
        args = dict(
            signing_key=MAC, expected_generation=generation,
            trusted_key_material=material,
        )
        args.update(overrides)
        return import_audit_keyring_state(blob, **args)

    def test_restore_original_and_rotated_keyring_without_secret_bytes(self):
        recovered = self.recover(self.old_blob, 1, {OLD.kid: OLD.secret})
        self.assertEqual(recovered.generation, 1)
        self.assertEqual(recovered.active_kid, OLD.kid)
        self.assertNotIn(OLD.secret, self.old_blob)

        self.assertEqual(self.ring.rotate(
            expected_generation=1, new_active=NEW, retain=(OLD.kid,),
        ), 2)
        overlap = export_audit_keyring_state(self.ring, signing_key=MAC)
        self.assertNotIn(OLD.secret, overlap)
        self.assertNotIn(NEW.secret, overlap)
        reopened = self.recover(overlap, 2, {
            OLD.kid: OLD.secret, NEW.kid: NEW.secret,
        })
        event = "finance-approval-audit-12"
        payload = {"event_id": event, "action": "consumed"}
        kid, signature = reopened.sign(
            namespace="ci_audit", event_id=event, payload=payload,
        )
        reopened.verify(
            namespace="ci_audit", event_id=event, payload=payload,
            kid=kid, signature=signature,
        )
        self.assertEqual(kid, NEW.kid)

    def test_external_generation_blocks_signed_old_snapshot(self):
        self.ring.rotate(expected_generation=1, new_active=NEW)
        current = export_audit_keyring_state(self.ring, signing_key=MAC)
        with self.assertRaises(FinanceAccessDenied):
            self.recover(self.old_blob, 2, {OLD.kid: OLD.secret})
        restored = self.recover(current, 2, {NEW.kid: NEW.secret})
        with self.assertRaises(FinanceAccessDenied):
            restored.rotate(expected_generation=2, new_active=OLD)

    def test_reject_payload_tampering_wrong_mac_or_key_substitution(self):
        for args in (
            {"blob": self.old_blob[:-1] + b" "},
            {"signing_key": b"wrong-mac-key-value-with-at-least-32bytes"},
            {"trusted_key_material": {OLD.kid: NEW.secret}},
            {"trusted_key_material": {OLD.kid: OLD.secret, NEW.kid: NEW.secret}},
            {"expected_generation": 2},
            {"expected_generation": True},
        ):
            with self.subTest(change=args):
                with self.assertRaises(FinanceAccessDenied):
                    self.recover(
                        args.get("blob", self.old_blob),
                        args.get("expected_generation", 1),
                        args.get("trusted_key_material", {OLD.kid: OLD.secret}),
                        signing_key=args.get("signing_key", MAC),
                    )
        envelope = json.loads(self.old_blob)
        envelope["state"]["retired"] = [OLD.kid]
        with self.assertRaises(FinanceAccessDenied):
            self.recover(json.dumps(envelope).encode(), 1,
                         {OLD.kid: OLD.secret})

    def test_signed_snapshot_preserves_revocation_tombstone(self):
        self.ring.rotate(expected_generation=1, new_active=NEW)
        blob = export_audit_keyring_state(self.ring, signing_key=MAC)
        recovered = self.recover(blob, 2, {NEW.kid: NEW.secret})
        self.assertEqual(recovered.active_kid, NEW.kid)
        with self.assertRaises(FinanceAccessDenied):
            recovered.rotate(expected_generation=2, new_active=OLD)


if __name__ == "__main__":
    unittest.main()
