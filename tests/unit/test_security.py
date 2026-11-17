from __future__ import annotations

import uuid

import jwt
import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.core.rate_limit import InMemoryRateLimiter
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)

SECRET = SecretStr("s" * 40)


def test_password_hashing() -> None:
    hashed = hash_password("Correct-Horse-1")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "Correct-Horse-1")
    assert not verify_password(hashed, "wrong")
    assert not verify_password(None, "anything")
    assert not verify_password("not-a-hash", "anything")


def test_access_token_roundtrip() -> None:
    settings = Settings(secret_key=SECRET)
    user_id = uuid.uuid4()
    token, _ = create_access_token(user_id=user_id, token_version=3, settings=settings)
    claims = decode_access_token(token, settings)
    assert claims.user_id == user_id
    assert claims.token_version == 3


def test_access_token_wrong_audience_rejected() -> None:
    issuer = Settings(secret_key=SECRET, jwt_audience="other-api")
    token, _ = create_access_token(user_id=uuid.uuid4(), token_version=0, settings=issuer)
    with pytest.raises(jwt.InvalidAudienceError):
        decode_access_token(token, Settings(secret_key=SECRET))


def test_refresh_tokens_are_random_and_hashed() -> None:
    a, b = generate_refresh_token(), generate_refresh_token()
    assert a != b
    assert len(a) >= 60
    assert hash_token(a) != a
    assert len(hash_token(a)) == 64


def test_rate_limiter_sliding_window() -> None:
    now = [0.0]
    limiter = InMemoryRateLimiter(2, 60, clock=lambda: now[0])
    assert limiter.hit("k") is None
    assert limiter.hit("k") is None
    assert limiter.hit("k") == 60
    assert limiter.hit("other") is None
    now[0] = 61
    assert limiter.hit("k") is None
    limiter.reset("k")
    assert limiter.hit("k") is None


def test_settings_validation() -> None:
    with pytest.raises(ValidationError):
        Settings(secret_key=SecretStr("too-short"))
    with pytest.raises(ValidationError, match="discord"):
        Settings(
            secret_key=SECRET, discord_webhook_url=SecretStr("https://evil.example/api/webhooks/1")
        )
    with pytest.raises(ValidationError, match="discord"):
        Settings(
            secret_key=SECRET, discord_webhook_url=SecretStr("http://discord.com/api/webhooks/1/x")
        )
    ok = Settings(
        secret_key=SECRET, discord_webhook_url=SecretStr("https://discord.com/api/webhooks/1/abc")
    )
    assert ok.discord_webhook_url is not None
    with pytest.raises(ValidationError, match="CORS"):
        Settings(secret_key=SECRET, environment="production", cors_origins=["*"])
