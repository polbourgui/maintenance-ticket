"""Security-related HTTP middleware."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
API_CSP = "default-src 'none'; frame-ancestors 'none'"
# Web app: only same-origin code; images may be blob: URLs (photos fetched with auth).
SPA_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; "
    "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, hsts: bool, api_prefix: str) -> None:
        super().__init__(app)
        self._hsts = hsts
        self._api_prefix = api_prefix

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        headers = response.headers
        path = request.url.path
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if path.startswith(self._api_prefix):
            headers.setdefault("Content-Security-Policy", API_CSP)
            headers.setdefault("Cache-Control", "no-store")
        elif not path.startswith(_DOCS_PATHS):
            # Swagger UI needs inline scripts/CDN assets, so it keeps the browser defaults.
            headers.setdefault("Content-Security-Policy", SPA_CSP)
        if self._hsts:
            headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response
