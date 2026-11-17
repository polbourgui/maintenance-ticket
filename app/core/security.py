"""Password hashing (Argon2id), JWT access tokens and opaque refresh tokens."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings

_hasher = PasswordHasher()  # Argon2id with OWASP-compliant defaults
# Used to spend the same CPU time when the user does not exist (prevents user enumeration).
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    token_version: int
    expires_at: datetime


def create_access_token(
    *, user_id: uuid.UUID, token_version: int, settings: Settings, now: datetime | None = None
) -> tuple[str, datetime]:
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "typ": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": issued_at,
        "nbf": issued_at,
        "exp": expires_at,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(
        payload, settings.secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return token, expires_at


def decode_access_token(token: str, settings: Settings) -> AccessTokenClaims:
    """Decode and fully validate an access token. Raises ``jwt.InvalidTokenError``."""
    payload = jwt.decode(
        token,
        settings.secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],  # never trust the "alg" header
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "nbf", "sub", "iss", "aud", "jti"]},
    )
    if payload.get("typ") != "access" or not isinstance(payload.get("ver"), int):
        raise jwt.InvalidTokenError("Invalid token type")
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except ValueError as exc:
        raise jwt.InvalidTokenError("Invalid subject") from exc
    return AccessTokenClaims(
        user_id=user_id,
        token_version=payload["ver"],
        expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
    )


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Refresh tokens are high-entropy, so a fast hash is sufficient (no salt needed)."""
    return hashlib.sha256(token.encode()).hexdigest()
