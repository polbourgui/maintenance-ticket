from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import AuthServiceDep, CurrentUser, SettingsDep
from app.core.config import Settings
from app.core.errors import AuthenticationError
from app.schemas.auth import PasswordChange, RefreshRequest, TokenPair
from app.schemas.common import ErrorResponse

router = APIRouter(prefix="/auth", tags=["Authentification"])

REFRESH_COOKIE = "refresh_token"
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE, include_in_schema=False)]


def _set_refresh_cookie(response: Response, pair: TokenPair, settings: Settings) -> None:
    """Browser clients keep the refresh token in an HttpOnly cookie, out of reach of JavaScript.

    SameSite=Strict + a path limited to the auth endpoints protect it against CSRF.
    """
    response.set_cookie(
        REFRESH_COOKIE,
        pair.refresh_token,
        max_age=settings.refresh_token_ttl_days * 86400,
        path=f"{settings.api_prefix}/auth",
        secure=settings.is_production,
        httponly=True,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=f"{settings.api_prefix}/auth",
        secure=settings.is_production,
        httponly=True,
        samesite="strict",
    )


def _refresh_token_from(body: RefreshRequest | None, cookie: str | None) -> str:
    token = body.refresh_token if body is not None else cookie
    if not token:
        raise AuthenticationError("Missing refresh token")
    return token


@router.post(
    "/login",
    response_model=TokenPair,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    summary="Authenticate (OAuth2 password flow) and open a session",
)
def login(
    request: Request,
    response: Response,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth: AuthServiceDep,
    settings: SettingsDep,
) -> TokenPair:
    """Returns the tokens in the body (API clients) and sets the refresh token as an
    HttpOnly cookie (browser clients)."""
    client_ip = request.client.host if request.client else "unknown"
    pair = auth.login(form.username, form.password, client_ip)
    _set_refresh_cookie(response, pair, settings)
    return pair


@router.post("/refresh", response_model=TokenPair, responses={401: {"model": ErrorResponse}})
def refresh(
    response: Response,
    auth: AuthServiceDep,
    settings: SettingsDep,
    cookie: RefreshCookie = None,
    body: RefreshRequest | None = None,
) -> TokenPair:
    """Rotate the refresh token (from the body, or else the HttpOnly cookie).
    Re-using an old refresh token revokes the whole session."""
    try:
        pair = auth.refresh(_refresh_token_from(body, cookie))
    except AuthenticationError:
        _clear_refresh_cookie(response, settings)
        raise
    _set_refresh_cookie(response, pair, settings)
    return pair


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    user: CurrentUser,
    auth: AuthServiceDep,
    settings: SettingsDep,
    cookie: RefreshCookie = None,
    body: RefreshRequest | None = None,
) -> None:
    token = body.refresh_token if body is not None else cookie
    if token:
        auth.logout(token, user)
    _clear_refresh_cookie(response, settings)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(
    response: Response, user: CurrentUser, auth: AuthServiceDep, settings: SettingsDep
) -> None:
    """Revoke every session and every access token of the current user."""
    auth.logout_everywhere(user)
    _clear_refresh_cookie(response, settings)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChange, user: CurrentUser, auth: AuthServiceDep) -> None:
    """Change password; all sessions (including the current one) are revoked."""
    auth.change_password(user, body.current_password, body.new_password)
