"""Network-free tests of mTLS transport request/response safety contract."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from https_floor_transport_candidate import HTTPSFloorTransportCandidate
from remote_generation_floor_candidate import RemoteGenerationFloorCandidate
from tenant_access import FinanceAccessDenied

HOST = "floor-ci.example"
ENDPOINT = "https://floor-ci.example/v1/floor"


class FakeSSL:
    minimum_version = None
    verify_mode = None
    check_hostname = None
    def load_cert_chain(self, *, certfile, keyfile):
        if (certfile, keyfile) != ("test-client.pem", "test-client-key.pem"):
            raise ValueError("test invalid cert")


class FakeResponse:
    def __init__(self, *, status=200, content_type="application/json", payload=None):
        self.status = status
        self.content_type = content_type
        self.payload = payload if payload is not None else b'{"namespace":"ci_tenant","generation":1,"status":"ok"}'

    def getheader(self, name):
        return self.content_type if name == "Content-Type" else None

    def read(self, length):
        return self.payload[:length]


class FakeConnection:
    def __init__(self, response, calls):
        self.response = response
        self.calls = calls
        self.closed = False

    def request(self, method, path, body, headers):
        self.calls.append((method, path, body, headers))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class HTTPSFloorTransportTests(unittest.TestCase):
    def setUp(self):
        self.connection = None
        self.requests = []
        self.response = FakeResponse()
        self.context = FakeSSL()
        def connection_factory(host, *, port, context, timeout):
            self.assertEqual((host, port), (HOST, 443))
            self.assertIs(context, self.context)
            self.assertEqual(timeout, 5)
            self.connection = FakeConnection(self.response, self.requests)
            return self.connection
        self.factory = connection_factory
        with patch("https_floor_transport_candidate.ssl.create_default_context",
                   return_value=self.context):
            self.transport = HTTPSFloorTransportCandidate(
                hostname=HOST, ca_bundle="ca.pem",
                client_cert="test-client.pem", client_key="test-client-key.pem",
                connection_factory=self.factory
            )

    def exchange(self, request=None, endpoint=ENDPOINT):
        return self.transport.exchange(
            endpoint=endpoint, timeout_seconds=5,
            request=request or {"operation": "read", "namespace": "ci_tenant"},
        )

    def test_valid_read_integrates_with_remote_floor_adapter(self):
        floor = RemoteGenerationFloorCandidate(
            endpoint=ENDPOINT, transport=self.transport
        )
        self.assertEqual(floor.read("ci_tenant"), 1)
        method, path, raw, headers = self.requests[0]
        self.assertEqual((method, path), ("POST", "/v1/floor"))
        self.assertEqual(json.loads(raw), {
            "operation": "read", "namespace": "ci_tenant"
        })
        self.assertNotIn("Authorization", headers)
        self.assertTrue(self.connection.closed)

    def test_cas_payload_and_server_confirmation(self):
        self.response = FakeResponse(payload=b'{"namespace":"ci_tenant","generation":2,"status":"advanced"}')
        floor = RemoteGenerationFloorCandidate(
            endpoint=ENDPOINT, transport=self.transport
        )
        self.assertTrue(floor.compare_and_advance("ci_tenant", 1, 2))
        self.assertEqual(json.loads(self.requests[0][2]), {
            "operation": "cas", "namespace": "ci_tenant",
            "expected_generation": 1, "next_generation": 2,
        })

    def test_redirect_error_content_type_size_and_json_rejected(self):
        responses = (
            FakeResponse(status=302),
            FakeResponse(status=401),
            FakeResponse(status=202),
            FakeResponse(status=204),
            FakeResponse(content_type="text/html"),
            FakeResponse(payload=b"x" * 4097),
            FakeResponse(payload=b""),
            FakeResponse(payload=b'{"a":1,"a":2}'),
            FakeResponse(payload=b'{"a": NaN}'),
            FakeResponse(payload=b"[]"),
        )
        for response in responses:
            with self.subTest(response=response):
                self.response = response
                with self.assertRaises(FinanceAccessDenied):
                    self.exchange()
                self.assertTrue(self.connection.closed)

    def test_no_connection_for_unpinned_endpoint_or_bad_request(self):
        for endpoint in (
            "http://floor-ci.example/v1/floor",
            "https://evil.example/v1/floor",
            "https://floor-ci.example:443/v1/floor",
            "https://floor-ci.example/v1/floor?x=1",
            "https://floor-ci.example/other",
            "https://user@floor-ci.example/v1/floor",
        ):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(FinanceAccessDenied):
                    self.exchange(endpoint=endpoint)
        for request in (
            {"operation": "read", "namespace": "../ci_tenant"},
            {"operation": "read", "namespace": "ci_tenant", "unexpected": 1},
            {"operation": "cas", "namespace": "ci_tenant",
             "expected_generation": True, "next_generation": 2},
            {"operation": "cas", "namespace": "ci_tenant",
             "expected_generation": 1, "next_generation": 3},
        ):
            with self.subTest(request=request):
                with self.assertRaises(FinanceAccessDenied):
                    self.exchange(request=request)
        self.assertEqual(self.requests, [])

    def test_constructor_rejects_ip_credentials_and_untrusted_host(self):
        for hostname in ("127.0.0.1", "localhost", "Floor-CI.Example",
                         "https://floor-ci.example", "floor-ci..example", ""):
            with self.subTest(host=hostname):
                with patch("https_floor_transport_candidate.ssl.create_default_context",
                           return_value=FakeSSL()):
                    with self.assertRaises(FinanceAccessDenied):
                        HTTPSFloorTransportCandidate(
                            hostname=hostname, ca_bundle="ca.pem",
                            client_cert="test-client.pem",
                            client_key="test-client-key.pem",
                            connection_factory=self.factory,
                        )


if __name__ == "__main__":
    unittest.main()
