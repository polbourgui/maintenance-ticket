from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import Settings
from app.core.errors import AuthenticationError, BusinessRuleError, RateLimitedError
from app.core.rate_limit import RateLimiter
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
)
from app.models import RefreshToken, User
from app.repositories import UnitOfWork
from app.schemas.auth import TokenPair

_INVALID_CREDENTIALS = "Invalid credentials"  # identical message for every failure: no enumeration


def validate_password_strength(
    password: str, settings: Settings, *, email: str | None = None
) -> None:
    if len(password) < settings.password_min_length:
        raise BusinessRuleError(
            f"Password must contain at least {settings.password_min_length} characters"
        )
    classes = sum(
        [
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        ]
    )
    if classes < 3:
        raise BusinessRuleError(
            "Password must mix at least 3 of: lowercase, uppercase, digits, symbols"
        )
    if email and email.split("@")[0].lower() in password.lower():
        raise BusinessRuleError("Password must not contain the e-mail address")


class AuthService:
    def __init__(self, uow: UnitOfWork, settings: Settings, rate_limiter: RateLimiter) -> None:
        self.uow = uow
        self.settings = settings
        self.rate_limiter = rate_limiter

    # -- login / sessions ---------------------------------------------------------------
    def login(self, email: str, password: str, client_ip: str) -> TokenPair:
        keys = (f"login:ip-email:{client_ip}:{email.lower()}", f"login:email:{email.lower()}")
        for key in keys:
            if (retry_after := self.rate_limiter.hit(key)) is not None:
                raise RateLimitedError("Too many login attempts, try again later", retry_after)

        user = self.uow.users.get_by_email(email)
        password_ok = verify_password(user.hashed_password if user else None, password)
        if user is None or not password_ok or not user.is_active:
            raise AuthenticationError(_INVALID_CREDENTIALS)

        for key in keys:
            self.rate_limiter.reset(key)
        if password_needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(password)
        now = datetime.now(UTC)
        user.last_login_at = now
        pair = self._issue(user, family_id=uuid.uuid4(), now=now)
        self.uow.commit()
        return pair

    def refresh(self, refresh_token: str) -> TokenPair:
        now = datetime.now(UTC)
        stored = self.uow.refresh_tokens.get_by_hash(hash_token(refresh_token))
        if stored is None:
            raise AuthenticationError("Invalid refresh token")
        if stored.revoked_at is not None:
            # Re-use of a rotated token: assume theft, kill the whole session family.
            self.uow.refresh_tokens.revoke_family(stored.family_id, now)
            self.uow.commit()
            raise AuthenticationError("Invalid refresh token")
        user = self.uow.users.get(stored.user_id)
        if stored.expires_at <= now or user is None or not user.is_active:
            raise AuthenticationError("Invalid refresh token")
        stored.revoked_at = now
        pair = self._issue(user, family_id=stored.family_id, now=now)
        self.uow.commit()
        return pair

    def logout(self, refresh_token: str, user: User) -> None:
        stored = self.uow.refresh_tokens.get_by_hash(hash_token(refresh_token))
        if stored is not None and stored.user_id == user.id:
            self.uow.refresh_tokens.revoke_family(stored.family_id, datetime.now(UTC))
            self.uow.commit()

    def logout_everywhere(self, user: User) -> None:
        self._invalidate_all_sessions(user)
        self.uow.commit()

    def change_password(self, user: User, current: str, new: str) -> None:
        if not verify_password(user.hashed_password, current):
            raise AuthenticationError(_INVALID_CREDENTIALS)
        validate_password_strength(new, self.settings, email=user.email)
        user.hashed_password = hash_password(new)
        self._invalidate_all_sessions(user)
        self.uow.commit()

    def authenticate(self, access_token: str) -> User:
        try:
            claims = decode_access_token(access_token, self.settings)
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("Invalid or expired token") from exc
        user = self.uow.users.get(claims.user_id)
        if user is None or not user.is_active or user.token_version != claims.token_version:
            raise AuthenticationError("Invalid or expired token")
        return user

    # -- helpers ------------------------------------------------------------------------
    def _invalidate_all_sessions(self, user: User) -> None:
        user.token_version += 1
        self.uow.refresh_tokens.revoke_all_for_user(user.id, datetime.now(UTC))

    def _issue(self, user: User, *, family_id: uuid.UUID, now: datetime) -> TokenPair:
        access, access_exp = create_access_token(
            user_id=user.id, token_version=user.token_version, settings=self.settings, now=now
        )
        raw_refresh = generate_refresh_token()
        refresh_exp = now + timedelta(days=self.settings.refresh_token_ttl_days)
        self.uow.refresh_tokens.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(raw_refresh),
                family_id=family_id,
                expires_at=refresh_exp,
            )
        )
        return TokenPair(
            access_token=access,
            expires_at=access_exp,
            refresh_token=raw_refresh,
            refresh_expires_at=refresh_exp,
        )
