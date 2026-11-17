from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import AuthenticationError, DomainError, RateLimitedError


async def _domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)  # noqa: S101 - narrowing for the type checker
    headers: dict[str, str] = {}
    if isinstance(exc, AuthenticationError):
        headers["WWW-Authenticate"] = "Bearer"
    if isinstance(exc, RateLimitedError):
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "detail": exc.message},
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error_handler)
