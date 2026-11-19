import time
import hmac
from collections import defaultdict, deque
from fastapi import Request, HTTPException
from config import cfg

# Per-IP sliding window: N=10 failures / W=300s → lockout for L=900s
_N = 10
_W = 300.0
_L = 900.0

_fail_times: dict[str, deque] = defaultdict(deque)
_lockout_until: dict[str, float] = {}


def _client_ip(request: Request) -> str:
    """The caller's IP for rate limiting. Proxy headers are client-controlled, so they are used
    only with TRUST_PROXY_HEADERS=true (behind our nginx), and then only the values our proxy
    itself writes: X-Real-IP (nginx overwrites it), else the LAST X-Forwarded-For hop (nginx
    appends; earlier hops can be forged by the client)."""
    if cfg.trust_proxy_headers:
        real = request.headers.get("X-Real-IP")
        if real:
            return real.strip()
        fwd = request.headers.get("X-Forwarded-For")
        if fwd:
            return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


client_ip = _client_ip


def _check_auth_rate(ip: str) -> tuple[bool, float]:
    now = time.monotonic()
    if ip in _lockout_until:
        remaining = _lockout_until[ip] - now
        if remaining > 0:
            return False, remaining
        del _lockout_until[ip]
    return True, 0.0


def _record_auth_fail(ip: str):
    now = time.monotonic()
    dq = _fail_times[ip]
    dq.append(now)
    # trim old entries outside the window
    while dq and dq[0] < now - _W:
        dq.popleft()
    if len(dq) >= _N:
        _lockout_until[ip] = now + _L


def _verify_token(token: str) -> bool:
    if not cfg.bearer_token:
        return False
    ok = hmac.compare_digest(token, cfg.bearer_token)
    # Accept previous token during rotation overlap window
    if not ok and cfg.bearer_token_prev:
        ok = hmac.compare_digest(token, cfg.bearer_token_prev)
    return ok


async def require_auth(request: Request):
    ip = _client_ip(request)

    allowed, retry_after = _check_auth_rate(ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts",
            headers={"Retry-After": str(int(retry_after))},
        )

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        _record_auth_fail(ip)
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = auth_header[len("Bearer "):]
    if not _verify_token(token):
        _record_auth_fail(ip)
        raise HTTPException(status_code=401, detail="Invalid token")
