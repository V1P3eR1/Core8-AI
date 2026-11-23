"""Isolated approval policy tests; all identities and ledgers are fake."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from key_approval_candidate import (
    IndependentApprovalLedger, ServerVerifiedOperator, StoredKeyApproval,
    authorize_and_rotate, proposal_hash, require_key_approval,
)
from tenant_access import FinanceAccessDenied


class FakeLedger(IndependentApprovalLedger):
    def __init__(self):
        self.records = {}
        self.used = set()
        self.consume_calls = 0

    def consume(self, approval_id, expected):
        self.consume_calls += 1
        record = self.records.get(approval_id)
        if approval_id in self.used or record != expected:
            return False
        self.used.add(approval_id)
        return True


class KeyApprovalCandidateTests(unittest.TestCase):
    def setUp(self):
        self.requester = ServerVerifiedOperator("manager_123", "key_manager")
        self.approver = ServerVerifiedOperator("security_456", "security_approver")
        self.jwks = {"keys": [{"kid": "new-ci-key"}]}
        self.now = 1770000000
        self.kwargs = {
            "namespace": "ci_keyring",
            "expected_generation": 3,
            "proposed_jwks": self.jwks,
            "retire": ("retired-ci-key",),
        }
        self.approval = StoredKeyApproval(
            approval_id="approved_12345678",
            requester_subject=self.requester.subject,
            approver_subject=self.approver.subject,
            proposal_sha256=proposal_hash(**self.kwargs),
            expires_at=self.now + 300,
        )
        self.ledger = FakeLedger()
        self.ledger.records[self.approval.approval_id] = self.approval

    def check(self, **overrides):
        values = dict(requester=self.requester, approver=self.approver,
                      approval=self.approval, now=self.now, **self.kwargs)
        values.update(overrides)
        return require_key_approval(**values)

    def rotate(self, **overrides):
        values = dict(
            ledger=self.ledger, requester=self.requester,
            approver=self.approver, approval=self.approval,
            conn=object(), signing_key=b"synthetic-ci-test-signing-key-strong-enough",
            floor=object(), now=self.now, **self.kwargs,
        )
        values.update(overrides)
        return authorize_and_rotate(**values)

    def test_valid_distinct_roles_and_approval_are_accepted(self):
        self.assertIsNone(self.check())
        with patch("external_floor_candidate.rotate_with_external_floor",
                   return_value=4) as apply:
            self.assertEqual(self.rotate(), 4)
            apply.assert_called_once()
        self.assertEqual(self.ledger.consume_calls, 1)

    def test_self_approval_and_invalid_roles_rejected(self):
        cases = [
            {"approver": ServerVerifiedOperator("manager_123", "security_approver")},
            {"requester": ServerVerifiedOperator("manager_123", "viewer")},
            {"approver": ServerVerifiedOperator("security_456", "key_manager")},
            {"requester": ServerVerifiedOperator("manager_123", "key_manager", False)},
            {"approver": ServerVerifiedOperator("security_456", "security_approver", False)},
            {"requester": "manager_123"},
            {"approver": None},
            {"requester": ServerVerifiedOperator("manager_123", [])},
            {"approver": ServerVerifiedOperator("security_456", {})},
        ]
        for args in cases:
            with self.subTest(args=args):
                with self.assertRaises(FinanceAccessDenied):
                    self.check(**args)

    def test_approval_cannot_be_reused_or_retargeted(self):
        with patch("external_floor_candidate.rotate_with_external_floor",
                   return_value=4) as apply:
            self.assertEqual(self.rotate(), 4)
            with self.assertRaises(FinanceAccessDenied):
                self.rotate()
            apply.assert_called_once()
        self.assertEqual(self.ledger.consume_calls, 2)
        for change in (
            {"namespace": "other_keyring"},
            {"expected_generation": 4},
            {"retire": ()},
            {"proposed_jwks": {"keys": [{"kid": "attacker"}]}},
        ):
            with self.subTest(change=change):
                with self.assertRaises(FinanceAccessDenied):
                    self.check(**change)

    def test_expired_or_bogus_approval_rejected_without_consuming(self):
        for bad in (
            replace(self.approval, expires_at=self.now),
            replace(self.approval, expires_at=self.now + 901),
            replace(self.approval, proposal_sha256="0" * 64),
            replace(self.approval, requester_subject="other_requester"),
            replace(self.approval, approver_subject="other_approver"),
            replace(self.approval, approval_id="bad id"),
        ):
            with self.subTest(approval=bad):
                with patch("external_floor_candidate.rotate_with_external_floor") as apply:
                    with self.assertRaises(FinanceAccessDenied):
                        self.rotate(approval=bad)
                    apply.assert_not_called()
        self.assertEqual(self.ledger.consume_calls, 0)

    def test_consumed_approval_stays_consumed_after_downstream_failure(self):
        with patch("external_floor_candidate.rotate_with_external_floor",
                   side_effect=RuntimeError("injected database outage")) as apply:
            with self.assertRaises(RuntimeError):
                self.rotate()
            with self.assertRaises(FinanceAccessDenied):
                self.rotate()
            apply.assert_called_once()
        self.assertEqual(self.ledger.consume_calls, 2)

    def test_untrusted_ledger_rejected(self):
        with patch("external_floor_candidate.rotate_with_external_floor") as apply:
            with self.assertRaises(FinanceAccessDenied):
                self.rotate(ledger={})
            apply.assert_not_called()

    def test_hash_is_canonical_for_retirement_order(self):
        alternative = proposal_hash(**{**self.kwargs,
            "retire": tuple(reversed(self.kwargs["retire"]))})
        self.assertEqual(self.approval.proposal_sha256, alternative)
        for invalid in (
            {"namespace": "../bad"},
            {"expected_generation": True},
            {"retire": ("repeated", "repeated")},
            {"proposed_jwks": {"keys": [], "nan": float("nan")}},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(FinanceAccessDenied):
                    proposal_hash(**{**self.kwargs, **invalid})


if __name__ == "__main__":
    unittest.main()
