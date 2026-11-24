"""Sandbox HTTPS transport for the remote generation-floor protocol.

This adapter performs HTTPS when called, but is NOT wired into an app, worker,
cron, production service or finance endpoint. The *operator* must pin a DNS
hostname, a trusted CA bundle and a client certificate/key from a protected
secret manager. A configured URL or certificate file is not evidence that an
external floor service exists or that its CAS is actually durable/linearizable.

No redirects, proxies, arbitrary ports, credential-bearing URLs, retries,
authentication headers, insecure TLS modes or non-HTTPS are supported.
"""
import http.client
import ipaddress
import json
import re
import ssl
from urllib.parse import urlsplit

from tenant_access import FinanceAccessDenied

_DNS = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")
_NAMESPACE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_ALLOWED_OPS = {"read", "cas"}
_MAX_RESPONSE = 4096


def _strict_json_pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("duplicate JSON key")
        out[k] = v
    return out


class HTTPSFloorTransportCandidate:
    """TLS1.2+ certificate-authenticated HTTPS JSON POST; no automatic retry.

    The cert/key remain on disk only as configured by the caller: they must
    be read-only and separately provisioned by the service operator.
    """

    def __init__(self, *, hostname, ca_bundle, client_cert, client_key,
                 connection_factory=None):
        try:
            if (any(type(s) is not str or not s for s in (
                    hostname, ca_bundle, client_cert, client_key))
                    or hostname != hostname.lower()
                    or not _DNS.fullmatch(hostname)
                    or ".." in hostname or "." not in hostname):
                raise ValueError("invalid pinned host or credentials")
            ipaddress.ip_address(hostname)
            raise ValueError("IP literal not allowed")
        except ValueError as e:
            if str(e) != "IP literal not allowed":
                # Failed IP parsing is expected for DNS names.
                if "does not appear to be" not in str(e):
                    raise FinanceAccessDenied("Finance HTTPS floor denied") from None
            else:
                raise FinanceAccessDenied("Finance HTTPS floor denied") from None
        try:
            ctx = ssl.create_default_context(
                purpose=ssl.Purpose.SERVER_AUTH, cafile=ca_bundle
            )
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.check_hostname = True
            ctx.load_cert_chain(certfile=client_cert, keyfile=client_key)
        except (OSError, ValueError, ssl.SSLError):
            raise FinanceAccessDenied("Finance HTTPS floor denied") from None
        self._host = hostname
        self._context = ctx
        self._connection_factory = (
            connection_factory if connection_factory is not None
            else http.client.HTTPSConnection
        )
        if not callable(self._connection_factory):
            raise FinanceAccessDenied("Finance HTTPS floor denied")

    def exchange(self, *, endpoint, request, timeout_seconds):
        conn = None
        try:
            if (type(endpoint) is not str or
                    type(timeout_seconds) not in (int, float) or
                    not 0.5 <= timeout_seconds <= 5 or
                    type(request) is not dict or
                    type(request.get("namespace")) is not str or
                    not _NAMESPACE.fullmatch(request["namespace"]) or
                    request.get("operation") not in _ALLOWED_OPS):
                raise ValueError("invalid request")
            parsed = urlsplit(endpoint)
            if (parsed.scheme != "https" or parsed.hostname != self._host
                    or parsed.netloc != self._host
                    or parsed.path != "/v1/floor"
                    or parsed.query or parsed.fragment):
                raise ValueError("endpoint not pinned")
            op = request["operation"]
            if op == "read":
                if set(request) != {"namespace", "operation"}:
                    raise ValueError("unexpected read fields")
            else:
                if set(request) != {"namespace", "operation",
                                    "expected_generation", "next_generation"}:
                    raise ValueError("unexpected CAS fields")
                expected = request["expected_generation"]
                proposed = request["next_generation"]
                if (type(expected) is not int or expected < 1
                        or type(proposed) is not int or
                        proposed != expected + 1 or proposed > 2**63 - 1):
                    raise ValueError("invalid CAS")
            body = json.dumps(
                request, sort_keys=True, separators=(",", ":"),
                allow_nan=False
            ).encode("ascii")
            if len(body) > 2048:
                raise ValueError("oversized request")
            conn = self._connection_factory(
                self._host, port=443, context=self._context,
                timeout=timeout_seconds
            )
            conn.request("POST", "/v1/floor", body=body, headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Cache-Control": "no-store",
            })
            response = conn.getresponse()
            # No redirects, authentication challenges, proxy responses or
            # ambiguous 202/204 statuses are accepted as a committed CAS.
            if response.status != 200:
                raise ValueError("untrusted HTTP status")
            content_type = response.getheader("Content-Type")
            if content_type != "application/json":
                raise ValueError("unexpected content type")
            payload = response.read(_MAX_RESPONSE + 1)
            if not 0 < len(payload) <= _MAX_RESPONSE:
                raise ValueError("response size invalid")
            result = json.loads(
                payload.decode("utf-8"),
                object_pairs_hook=_strict_json_pairs,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NaN")),
            )
            if type(result) is not dict:
                raise ValueError("invalid response")
            return result
        except Exception:
            raise FinanceAccessDenied("Finance HTTPS floor denied") from None
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
