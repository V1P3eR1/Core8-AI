"""Offline fail-closed external generation floor contract tests.

The fake floor intentionally lives only in this test. This does not implement
a durable or authenticated production watermark service.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from external_floor_candidate import (
    IndependentGenerationFloor, recover_with_external_floor,
    rotate_with_external_floor,
)
from tenant_access import FinanceAccessDenied


class FakeIndependentFloor(IndependentGenerationFloor):
    def __init__(self, generation=1, *, allow=True):
        self.generation = generation
        self.allow = allow
        self.calls = []

    def read(self, namespace):
        self.calls.append(("read", namespace))
        return self.generation

    def compare_and_advance(self, namespace, expected_generation, next_generation):
        self.calls.append(("cas", namespace, expected_generation, next_generation))
        if not self.allow or self.generation != expected_generation:
            return False
        self.generation = next_generation
        return True


class FakeRegistry:
    def __init__(self, generation):
        self.generation = generation

    def snapshot(self):
        return self.generation, {"keys": [{"kid": "ci"}]}

    def preview_replace(self, jwks, *, generation, retire=()):
        if type(jwks) is not dict or type(jwks.get("keys")) is not list:
            raise FinanceAccessDenied("Finance key configuration denied")
        if retire and "ci" in retire:
            raise FinanceAccessDenied("Finance key configuration denied")
        if generation != self.generation + 1:
            raise FinanceAccessDenied("Finance key configuration denied")
        return True


class ExternalFloorPolicyTests(unittest.TestCase):
    def setUp(self):
        self.floor = FakeIndependentFloor()
        self.conn = object()
        self.kwargs = {
            "namespace": "ci_keys",
            "signing_key": b"sandbox-only-test-authenticated-key-long-enough",
        }

    def test_recovery_requires_externally_fetched_generation(self):
        with patch("external_floor_candidate.recover_jwks_store",
                   return_value=FakeRegistry(1)) as recover:
            result = recover_with_external_floor(
                self.conn, **self.kwargs, floor=self.floor
            )
        self.assertEqual(result.generation, 1)
        self.assertEqual(self.floor.calls, [("read", "ci_keys")])
        self.assertEqual(recover.call_args.kwargs["minimum_generation"], 1)

    def test_reject_untrusted_or_missing_floor_without_database_read(self):
        for floor in (None, object(), {}, "1"):
            with self.subTest(floor=floor):
                with patch("external_floor_candidate.recover_jwks_store") as read:
                    with self.assertRaises(FinanceAccessDenied):
                        recover_with_external_floor(
                            self.conn, **self.kwargs, floor=floor
                        )
                    read.assert_not_called()

    def test_reject_malformed_and_unavailable_external_floor(self):
        for number in (None, 0, True, "1", -1):
            with self.subTest(number=number):
                with patch("external_floor_candidate.recover_jwks_store") as read:
                    with self.assertRaises(FinanceAccessDenied):
                        recover_with_external_floor(
                            self.conn, **self.kwargs,
                            floor=FakeIndependentFloor(number)
                        )
                    read.assert_not_called()

    def test_stale_expected_generation_never_advances_floor(self):
        floor = FakeIndependentFloor(3)
        with patch("external_floor_candidate.recover_jwks_store") as read:
            with self.assertRaises(FinanceAccessDenied):
                rotate_with_external_floor(
                    self.conn, **self.kwargs, floor=floor,
                    expected_generation=2, proposed_jwks={"keys": []},
                )
            read.assert_not_called()
        self.assertEqual(floor.generation, 3)

    def test_successful_rotation_advances_floor_before_db_write(self):
        events = []
        class OrderedFloor(FakeIndependentFloor):
            def compare_and_advance(self, *args):
                events.append("floor")
                return super().compare_and_advance(*args)
        floor = OrderedFloor()
        def db_rotate(*args, **kwargs):
            events.append("db")
            return 2
        with patch("external_floor_candidate.recover_jwks_store",
                   return_value=FakeRegistry(1)), patch(
                       "external_floor_candidate.rotate_jwks_store",
                       side_effect=db_rotate
                   ):
            result = rotate_with_external_floor(
                self.conn, **self.kwargs, floor=floor,
                expected_generation=1, proposed_jwks={"keys": []},
            )
        self.assertEqual(result, 2)
        self.assertEqual(events, ["floor", "db"])
        self.assertEqual(floor.generation, 2)

    def test_invalid_rotation_cannot_advance_external_floor(self):
        for proposed, retired in ((None, ()), ({"bad": []}, ()),
                                  ({"keys": []}, ("ci",))):
            floor = FakeIndependentFloor()
            with self.subTest(proposed=proposed, retired=retired), patch(
                "external_floor_candidate.recover_jwks_store",
                return_value=FakeRegistry(1)
            ), patch("external_floor_candidate.rotate_jwks_store") as write:
                with self.assertRaises(FinanceAccessDenied):
                    rotate_with_external_floor(
                        self.conn, **self.kwargs, floor=floor,
                        expected_generation=1, proposed_jwks=proposed,
                        retire=retired,
                    )
                write.assert_not_called()
            self.assertEqual(floor.generation, 1)
            self.assertEqual(
                [entry for entry in floor.calls if entry[0] == "cas"], []
            )

    def test_external_cas_denial_never_writes_database(self):
        self.floor.allow = False
        with patch("external_floor_candidate.recover_jwks_store",
                   return_value=FakeRegistry(1)), patch(
                       "external_floor_candidate.rotate_jwks_store"
                   ) as rotate:
            with self.assertRaises(FinanceAccessDenied):
                rotate_with_external_floor(
                    self.conn, **self.kwargs, floor=self.floor,
                    expected_generation=1, proposed_jwks={"keys": []},
                )
            rotate.assert_not_called()
        self.assertEqual(self.floor.generation, 1)

    def test_database_failure_after_floor_advance_is_fail_closed(self):
        with patch("external_floor_candidate.recover_jwks_store",
                   return_value=FakeRegistry(1)), patch(
                       "external_floor_candidate.rotate_jwks_store",
                       side_effect=RuntimeError("synthetic database outage")
                   ):
            with self.assertRaisesRegex(RuntimeError, "synthetic database outage"):
                rotate_with_external_floor(
                    self.conn, **self.kwargs, floor=self.floor,
                    expected_generation=1, proposed_jwks={"keys": []},
                )
        self.assertEqual(self.floor.generation, 2)
        with patch("external_floor_candidate.recover_jwks_store",
                   side_effect=FinanceAccessDenied("older signed database snapshot")):
            with self.assertRaises(FinanceAccessDenied):
                recover_with_external_floor(
                    self.conn, **self.kwargs, floor=self.floor
                )


if __name__ == "__main__":
    unittest.main()
