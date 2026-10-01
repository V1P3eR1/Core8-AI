import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_DEV_MODE = os.getenv("DEV_MODE", "false").lower() in ("true", "1", "yes")

_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self' ws://localhost:8000 wss://localhost:8000 {ws_origin}; "
    "font-src 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none';"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # Report-only in dev so errors are visible; enforcing in production
        origin = os.getenv("ALLOWED_ORIGIN", "")
        ws_origin = f"wss://{origin.replace('https://', '')}" if origin else ""
        csp = _CSP.format(ws_origin=ws_origin)
        header = "Content-Security-Policy-Report-Only" if _DEV_MODE else "Content-Security-Policy"
        response.headers[header] = csp
        if not _DEV_MODE:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response
