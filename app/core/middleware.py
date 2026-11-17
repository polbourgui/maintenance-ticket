"""Security-related HTTP middleware."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        super().__init__(app)
        self._hsts = hsts

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if not request.url.path.startswith(_DOCS_PATHS):
            # Swagger UI needs inline scripts/CDN assets; every other route is pure API.
            headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )
            headers.setdefault("Cache-Control", "no-store")
        if self._hsts:
            headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response
