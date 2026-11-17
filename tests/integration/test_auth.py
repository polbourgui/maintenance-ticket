from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import jwt

from app.core.config import Settings
from app.core.security import create_access_token
from tests.conftest import World, auth_headers
from tests.helpers import PASSWORD

API = "/api/v1"


def _login(world: World, email: str, password: str = PASSWORD) -> httpx.Response:
    response: httpx.Response = world.client.post(
        f"{API}/auth/login", data={"username": email, "password": password}
    )
    return response


def test_login_returns_token_pair(world: World) -> None:
    r = _login(world, "TECH.A@example.org")  # e-mail is case-insensitive
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    me = world.client.get(
        f"{API}/users/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.json()["email"] == "tech.a@example.org"


def test_login_failures_are_indistinguishable(world: World) -> None:
    unknown = _login(world, "nobody@example.org")
    wrong = _login(world, "tech.a@example.org", "Wrong-Passw0rd!")
    assert unknown.status_code == wrong.status_code == 401
    assert (
        unknown.json()
        == wrong.json()
        == {"code": "authentication_failed", "detail": "Invalid credentials"}
    )


def test_login_rate_limited(world: World) -> None:
    for _ in range(3):
        assert _login(world, "tech.a@example.org", "bad").status_code == 401
    r = _login(world, "tech.a@example.org", PASSWORD)  # even the right password is throttled
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0


def test_refresh_rotation_and_reuse_detection(world: World) -> None:
    first = _login(world, "tech.a@example.org").json()
    r = world.client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 200
    second = r.json()
    assert second["refresh_token"] != first["refresh_token"]

    # Replaying the rotated token = theft signal -> whole family revoked
    replay = world.client.post(
        f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert replay.status_code == 401
    r = world.client.post(f"{API}/auth/refresh", json={"refresh_token": second["refresh_token"]})
    assert r.status_code == 401


def test_logout_revokes_refresh_token(world: World) -> None:
    tokens = _login(world, "tech.a@example.org").json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    r = world.client.post(
        f"{API}/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=headers
    )
    assert r.status_code == 204
    r = world.client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


def test_logout_all_invalidates_access_tokens(world: World) -> None:
    h1 = auth_headers(world.client, "tech.a@example.org")
    h2 = auth_headers(world.client, "tech.a@example.org")
    assert world.client.post(f"{API}/auth/logout-all", headers=h1).status_code == 204
    assert world.client.get(f"{API}/users/me", headers=h1).status_code == 401
    assert world.client.get(f"{API}/users/me", headers=h2).status_code == 401


def test_password_change(world: World) -> None:
    h = auth_headers(world.client, "tech.a@example.org")
    r = world.client.post(
        f"{API}/auth/password",
        json={"current_password": "wrong", "new_password": "N3w-Passw0rd-OK"},
        headers=h,
    )
    assert r.status_code == 401
    r = world.client.post(
        f"{API}/auth/password",
        json={"current_password": PASSWORD, "new_password": "short"},
        headers=h,
    )
    assert r.status_code == 422
    r = world.client.post(
        f"{API}/auth/password",
        json={"current_password": PASSWORD, "new_password": "N3w-Passw0rd-OK"},
        headers=h,
    )
    assert r.status_code == 204
    assert world.client.get(f"{API}/users/me", headers=h).status_code == 401  # sessions revoked
    assert _login(world, "tech.a@example.org", "N3w-Passw0rd-OK").status_code == 200


def test_tampered_and_forged_tokens_rejected(world: World, settings: Settings) -> None:
    token = _login(world, "tech.a@example.org").json()["access_token"]
    header, payload, sig = token.split(".")
    tampered = f"{header}.{payload}.{sig[:-2]}AA"
    assert (
        world.client.get(
            f"{API}/users/me", headers={"Authorization": f"Bearer {tampered}"}
        ).status_code
        == 401
    )

    forged = jwt.encode(
        {"sub": str(world.admin.id), "ver": 0},
        "another-secret-of-sufficient-length!!",
        algorithm="HS256",
    )
    assert (
        world.client.get(
            f"{API}/users/me", headers={"Authorization": f"Bearer {forged}"}
        ).status_code
        == 401
    )

    unsigned = jwt.encode({"sub": str(world.admin.id), "ver": 0}, key=None, algorithm="none")
    assert (
        world.client.get(
            f"{API}/users/me", headers={"Authorization": f"Bearer {unsigned}"}
        ).status_code
        == 401
    )


def test_expired_token_rejected(world: World, settings: Settings) -> None:
    token, _ = create_access_token(
        user_id=world.tech_a.id,
        token_version=0,
        settings=settings,
        now=datetime.now(UTC) - timedelta(hours=2),
    )
    assert (
        world.client.get(
            f"{API}/users/me", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 401
    )
