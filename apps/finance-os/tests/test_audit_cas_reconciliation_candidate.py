"""Offline loss-of-CAS-ACK regression tests; never retries external writes."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_cas_reconciliation_candidate import reconcile_lost_cas_ack
from remote_generation_floor_candidate import RemoteGenerationFloorCandidate
from tenant_access import FinanceAccessDenied


class FakeTransport:
    def __init__(self, *, generation=1):
        self.generation = generation
        self.calls = []
        self.drop_cas_response = False
        self.raise_on_read = False

    def exchange(self, *, endpoint, request, timeout_seconds):
        self.calls.append(request.copy())
        if request["operation"] == "read":
            if self.raise_on_read:
                raise TimeoutError("synthetic offline read failure")
            return {"namespace": request["namespace"], "status": "ok",
                    "generation": self.generation}
        if request["operation"] != "cas":
            raise AssertionError("unknown request")
        if self.generation == request["expected_generation"]:
            self.generation = request["next_generation"]
        if self.drop_cas_response:
            raise TimeoutError("synthetic lost CAS acknowledgment")
        return {"namespace": request["namespace"], "status": "advanced",
                "generation": self.generation}


class LostCasAckCandidateTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.floor = RemoteGenerationFloorCandidate(
            endpoint="https://audit-floor.example/v1/floor",
            transport=self.transport,
        )
        self.namespace = "ci_cas"

    def reconcile(self, expected=1, requested=2):
        return reconcile_lost_cas_ack(
            floor=self.floor, namespace=self.namespace,
            expected_generation=expected, requested_generation=requested,
        )

    def test_server_commits_then_ack_lost_read_only_followup(self):
        self.transport.drop_cas_response = True
        with self.assertRaises(FinanceAccessDenied):
            self.floor.compare_and_advance(self.namespace, 1, 2)
        result = self.reconcile()
        self.assertEqual((result.status, result.observed_generation),
                         ("advanced_or_later", 2))
        self.assertEqual([v["operation"] for v in self.transport.calls],
                         ["cas", "read"])
        self.assertEqual(self.transport.generation, 2)

    def test_no_server_commit_read_reports_unchanged(self):
        result = self.reconcile()
        self.assertEqual((result.status, result.observed_generation),
                         ("unchanged", 1))
        self.assertEqual([x["operation"] for x in self.transport.calls], ["read"])

    def test_other_writer_advance_is_not_attributed_to_original_cas(self):
        self.transport.generation = 3
        result = self.reconcile()
        self.assertEqual(result.status, "advanced_or_later")
        self.assertEqual(result.observed_generation, 3)
        self.assertEqual(len(self.transport.calls), 1)

    def test_read_outage_reports_unavailable_without_writes(self):
        self.transport.raise_on_read = True
        result = self.reconcile()
        self.assertEqual((result.status, result.observed_generation),
                         ("unavailable", None))
        self.assertEqual([x["operation"] for x in self.transport.calls], ["read"])

    def test_floor_rollback_and_invalid_input_fail_closed(self):
        for floor, namespace, expected, requested in (
            (object(), self.namespace, 1, 2),
            (self.floor, "../wrong", 1, 2),
            (self.floor, self.namespace, True, 2),
            (self.floor, self.namespace, 1, 3),
            (self.floor, self.namespace, 0, 1),
        ):
            with self.subTest(args=(namespace, expected, requested)):
                with self.assertRaises(FinanceAccessDenied):
                    reconcile_lost_cas_ack(
                        floor=floor, namespace=namespace,
                        expected_generation=expected,
                        requested_generation=requested,
                    )
        self.assertEqual(self.transport.calls, [])
        self.transport.generation = 1
        with self.assertRaises(FinanceAccessDenied):
            self.reconcile(expected=2, requested=3)
        self.assertEqual([x["operation"] for x in self.transport.calls], ["read"])


if __name__ == "__main__":
    unittest.main()
