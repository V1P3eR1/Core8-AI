"""Review-only recovery tests; all secrets synthetic and local to CI."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_key_rotation_candidate import AuditKeyringCandidate, PinnedAuditKey
from audit_key_state_candidate import (
    export_audit_keyring_state, import_audit_keyring_state,
)
from tenant_access import FinanceAccessDenied

OLD = PinnedAuditKey("key_old", b"synthetic-old-audit-delivery-key-material-32bytes")
NEW = PinnedAuditKey("key_new", b"synthetic-new-audit-delivery-key-material-32bytes")
THIRD = PinnedAuditKey("key_third", b"synthetic-third-audit-delivery-key-material-32bytes")
STATE_KEY = b"test-only-independent-state-hmac-key-material-32bytes"


class AuditKeyStateCandidateTests(unittest.TestCase):
    def setUp(self):
        self.ring = AuditKeyringCandidate(active=OLD)
        self.ring.rotate(expected_generation=1, new_active=NEW,
                         retain=(OLD.kid,))
        self.ring.rotate(expected_generation=2, new_active=NEW)
        self.namespace = "ci_audit_state"
        self.blob = export_audit_keyring_state(
            self.ring, namespace=self.namespace,
            state_signing_key=STATE_KEY,
        )

    def restore(self, **overrides):
        params = dict(
            blob=self.blob, namespace=self.namespace,
            state_signing_key=STATE_KEY, minimum_generation=3,
            pinned_secrets={NEW.kid: NEW.secret},
        )
        params.update(overrides)
        return import_audit_keyring_state(**params)

    def test_restart_restores_revoked_tombstone_without_exporting_keys(self):
        for secret in (OLD.secret, NEW.secret, STATE_KEY):
            self.assertNotIn(secret, self.blob)
            self.assertNotIn(secret.hex().encode(), self.blob)
        recovered = self.restore()
        self.assertEqual(recovered.generation, 3)
        self.assertEqual(recovered.active_kid, NEW.kid)
        with self.assertRaises(FinanceAccessDenied):
            recovered.rotate(expected_generation=3, new_active=OLD)
        self.assertEqual(recovered.rotate(
            expected_generation=3, new_active=THIRD, retain=(NEW.kid,)
        ), 4)

    def test_state_cannot_restore_against_independent_newer_floor(self):
        for floor in (2, 4, True):
            with self.subTest(floor=floor):
                with self.assertRaises(FinanceAccessDenied):
                    self.restore(minimum_generation=floor)

    def test_wrong_namespace_wrong_signing_key_or_secret_fail_closed(self):
        for args in (
            {"namespace": "another_namespace"},
            {"state_signing_key": b"incorrect-state-hmac-key-32-bytes-testonly"},
            {"pinned_secrets": {NEW.kid: OLD.secret}},
            {"pinned_secrets": {NEW.kid: NEW.secret, OLD.kid: OLD.secret}},
            {"pinned_secrets": {}},
            {"pinned_secrets": {NEW.kid: "fake"}},
        ):
            with self.subTest(args=str(args)[:100]):
                with self.assertRaises(FinanceAccessDenied):
                    self.restore(**args)

    def test_tamper_any_signed_field_rejected(self):
        envelope = json.loads(self.blob)
        for value in (
            {"generation": 4},
            {"active": OLD.kid},
            {"retired": []},
            {"verify_only": [OLD.kid]},
            {"proofs": {NEW.kid: "0" * 64}},
            {"namespace": "some_other"},
        ):
            with self.subTest(value=value):
                attempt = json.loads(self.blob)
                attempt["state"].update(value)
                raw = json.dumps(attempt).encode()
                with self.assertRaises(FinanceAccessDenied):
                    self.restore(blob=raw)
        with self.assertRaises(FinanceAccessDenied):
            self.restore(blob=b"not-json")

    def test_overlap_keys_are_reconstructed_from_trusted_inputs(self):
        overlap = AuditKeyringCandidate(active=OLD)
        overlap.rotate(expected_generation=1, new_active=NEW,
                       retain=(OLD.kid,))
        blob = export_audit_keyring_state(
            overlap, namespace=self.namespace,
            state_signing_key=STATE_KEY,
        )
        recovered = self.restore(
            blob=blob, minimum_generation=2,
            pinned_secrets={NEW.kid: NEW.secret, OLD.kid: OLD.secret},
        )
        kid, tag = recovered.sign(
            namespace=self.namespace,
            event_id="finance-approval-audit-102",
            payload={"event_id": "finance-approval-audit-102"},
        )
        self.assertEqual(kid, NEW.kid)
        recovered.verify(
            namespace=self.namespace,
            event_id="finance-approval-audit-102",
            payload={"event_id": "finance-approval-audit-102"},
            kid=kid, signature=tag,
        )


if __name__ == "__main__":
    unittest.main()
