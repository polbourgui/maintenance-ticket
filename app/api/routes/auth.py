from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import AuthServiceDep, CurrentUser
from app.schemas.auth import PasswordChange, RefreshRequest, TokenPair
from app.schemas.common import ErrorResponse

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post(
    "/login",
    response_model=TokenPair,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    summary="Authenticate (OAuth2 password flow) and open a session",
)
def login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth: AuthServiceDep,
) -> TokenPair:
    client_ip = request.client.host if request.client else "unknown"
    return auth.login(form.username, form.password, client_ip)


@router.post("/refresh", response_model=TokenPair, responses={401: {"model": ErrorResponse}})
def refresh(body: RefreshRequest, auth: AuthServiceDep) -> TokenPair:
    """Rotate the refresh token. Re-using an old refresh token revokes the whole session."""
    return auth.refresh(body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest, user: CurrentUser, auth: AuthServiceDep) -> None:
    auth.logout(body.refresh_token, user)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(user: CurrentUser, auth: AuthServiceDep) -> None:
    """Revoke every session and every access token of the current user."""
    auth.logout_everywhere(user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChange, user: CurrentUser, auth: AuthServiceDep) -> None:
    """Change password; all sessions (including the current one) are revoked."""
    auth.change_password(user, body.current_password, body.new_password)
