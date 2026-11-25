"""Offline contract tests for a prospective independently hosted floor service."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from remote_generation_floor_candidate import RemoteGenerationFloorCandidate
from tenant_access import FinanceAccessDenied


class InProcessFakeTransport:
    """The fixture models a server response; it is NOT HTTPS or authentication."""
    def __init__(self):
        self.generation = {"ci_tenant_one": 1}
        self.calls = []
        self.error = None
        self.mutate_response = None

    def exchange(self, *, endpoint, request, timeout_seconds):
        self.calls.append((endpoint, dict(request), timeout_seconds))
        if self.error is not None:
            raise self.error
        namespace = request["namespace"]
        if namespace not in self.generation:
            return {"namespace": namespace, "status": "missing", "generation": 1}
        old = self.generation[namespace]
        if request["operation"] == "read":
            response = {"namespace": namespace, "status": "ok", "generation": old}
        elif request["operation"] == "cas":
            if request["expected_generation"] == old:
                self.generation[namespace] = request["next_generation"]
                response = {"namespace": namespace, "status": "advanced",
                            "generation": self.generation[namespace]}
            else:
                response = {"namespace": namespace, "status": "conflict",
                            "generation": old}
        else:
            raise ValueError("unexpected operation")
        return self.mutate_response if self.mutate_response is not None else response


class RemoteFloorContractTests(unittest.TestCase):
    def setUp(self):
        self.transport = InProcessFakeTransport()
        self.floor = RemoteGenerationFloorCandidate(
            endpoint="https://isolated-floor.example/v1/floor",
            transport=self.transport,
        )

    def test_read_cas_and_stale_conflict(self):
        self.assertEqual(self.floor.read("ci_tenant_one"), 1)
        self.assertTrue(self.floor.compare_and_advance("ci_tenant_one", 1, 2))
        self.assertEqual(self.floor.read("ci_tenant_one"), 2)
        self.assertFalse(self.floor.compare_and_advance("ci_tenant_one", 1, 2))
        self.assertEqual(self.transport.calls[1][2], 5)
        self.assertEqual(self.transport.calls[1][1], {
            "operation": "cas", "namespace": "ci_tenant_one",
            "expected_generation": 1, "next_generation": 2,
        })

    def test_no_requests_for_invalid_namespace_or_generation(self):
        for ns in ("../ci_tenant_one", "CI_BAD", "", None):
            with self.subTest(ns=ns), self.assertRaises(FinanceAccessDenied):
                self.floor.read(ns)
        for old, new in ((True, 2), (0, 1), (1, 3), (1, True),
                         (2**63 - 1, 2**63)):
            with self.subTest(version=(old, new)), self.assertRaises(FinanceAccessDenied):
                self.floor.compare_and_advance("ci_tenant_one", old, new)
        self.assertEqual(self.transport.calls, [])

    def test_fail_closed_untrusted_response_and_transport_outage(self):
        self.transport.error = TimeoutError("offline fixture")
        with self.assertRaises(FinanceAccessDenied):
            self.floor.read("ci_tenant_one")
        self.transport.error = None
        for response in (
            {"namespace": "ci_other", "status": "ok", "generation": 1},
            {"namespace": "ci_tenant_one", "status": "ok", "generation": True},
            {"namespace": "ci_tenant_one", "status": "advanced", "generation": 1},
            {"namespace": "ci_tenant_one", "status": "ok", "generation": 1,
             "secret": "unexpected"},
            ["not a response"], 42,
        ):
            with self.subTest(response=response):
                self.transport.mutate_response = response
                with self.assertRaises(FinanceAccessDenied):
                    self.floor.read("ci_tenant_one")
        self.transport.mutate_response = None
        self.assertEqual(self.floor.read("ci_tenant_one"), 1)

    def test_reject_ambiguous_cas_ack_and_false_conflict(self):
        for status, generation in (
            ("advanced", 1), ("ok", 2), ("conflict", 0),
            ("conflict", 1 - 1), ("conflict", 1), ("unknown", 2)
        ):
            with self.subTest(status=status, generation=generation):
                self.transport.mutate_response = {
                    "namespace": "ci_tenant_one", "status": status,
                    "generation": generation,
                }
                with self.assertRaises(FinanceAccessDenied):
                    self.floor.compare_and_advance("ci_tenant_one", 1, 2)

    def test_https_only_and_no_uri_credentials_or_query(self):
        for endpoint in (
            "http://isolated-floor.example/v1/floor",
            "https://user:pass@isolated-floor.example/v1/floor",
            "https://isolated-floor.example/v1/floor?token=unsafe",
            "https://isolated-floor.example:8443/v1/floor",
            "https://isolated-floor.example/evil",
            "https://isolated-floor.example/v1/floor#frag",
            "https://isolated-floor.example:invalid/v1/floor",
            None,
        ):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(FinanceAccessDenied):
                    RemoteGenerationFloorCandidate(endpoint=endpoint,
                                                   transport=self.transport)
        with self.assertRaises(FinanceAccessDenied):
            RemoteGenerationFloorCandidate(
                endpoint="https://isolated-floor.example/v1/floor",
                transport=object(),
            )


if __name__ == "__main__":
    unittest.main()
