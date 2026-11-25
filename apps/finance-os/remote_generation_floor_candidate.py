"""Unwired HTTPS floor-client contract for sandbox-only integration testing.

A production deployment needs an independently administered service with
authenticated, linearizable CAS, server-side authorization, replay protection,
durable monotonic storage and TLS verification. This module does NOT make HTTP
requests. It accepts a trusted injected transport in unit tests; the returned
data is not itself proof of independence or authenticity.
"""
import re
from urllib.parse import urlsplit

from external_floor_candidate import IndependentGenerationFloor
from tenant_access import FinanceAccessDenied

_NAMESPACE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")


class RemoteGenerationFloorCandidate(IndependentGenerationFloor):
    """Strict response-schema adapter; transport must enforce TLS and identity."""

    def __init__(self, *, endpoint, transport):
        if type(endpoint) is not str:
            raise FinanceAccessDenied("Finance remote floor denied")
        try:
            url = urlsplit(endpoint)
            if (url.scheme != "https" or not url.hostname or url.username or
                    url.password or url.port not in (None, 443) or
                    url.query or url.fragment or url.path not in ("", "/v1/floor")):
                raise ValueError("unsafe endpoint")
        except (ValueError, TypeError):
            raise FinanceAccessDenied("Finance remote floor denied") from None
        if transport is None or not callable(getattr(transport, "exchange", None)):
            raise FinanceAccessDenied("Finance remote floor denied")
        self._endpoint = endpoint.rstrip("/")
        self._transport = transport

    @staticmethod
    def _check_namespace(namespace):
        if type(namespace) is not str or not _NAMESPACE.fullmatch(namespace):
            raise FinanceAccessDenied("Finance remote floor denied")

    @staticmethod
    def _check_generation(generation):
        if type(generation) is not int or generation < 1 or generation > 2**63 - 1:
            raise FinanceAccessDenied("Finance remote floor denied")

    def _exchange(self, *, operation, namespace, expected=None, next_generation=None):
        # Trusted transport contract: exchange MUST establish server identity
        # and sender authorization, reject redirects and enforce timeouts.
        request = {"operation": operation, "namespace": namespace}
        if expected is not None:
            request.update(expected_generation=expected,
                           next_generation=next_generation)
        try:
            response = self._transport.exchange(
                endpoint=self._endpoint, request=request, timeout_seconds=5,
            )
        except Exception:
            raise FinanceAccessDenied("Finance remote floor denied") from None
        if (type(response) is not dict or
                set(response) != {"namespace", "generation", "status"} or
                response["namespace"] != namespace):
            raise FinanceAccessDenied("Finance remote floor denied")
        self._check_generation(response["generation"])
        if type(response["status"]) is not str:
            raise FinanceAccessDenied("Finance remote floor denied")
        return response

    def read(self, namespace):
        self._check_namespace(namespace)
        response = self._exchange(operation="read", namespace=namespace)
        if response["status"] != "ok":
            raise FinanceAccessDenied("Finance remote floor denied")
        return response["generation"]

    def compare_and_advance(self, namespace, expected_generation, next_generation):
        self._check_namespace(namespace)
        self._check_generation(expected_generation)
        self._check_generation(next_generation)
        if next_generation != expected_generation + 1:
            raise FinanceAccessDenied("Finance remote floor denied")
        response = self._exchange(
            operation="cas", namespace=namespace,
            expected=expected_generation, next_generation=next_generation,
        )
        if (response["status"] == "advanced" and
                response["generation"] == next_generation):
            return True
        if (response["status"] == "conflict" and
                response["generation"] > expected_generation):
            return False
        raise FinanceAccessDenied("Finance remote floor denied")
