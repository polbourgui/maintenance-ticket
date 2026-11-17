"""Browser-oriented behaviour: HttpOnly refresh cookie, display names, SPA hosting."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.db.base import Base
from app.main import create_app
from tests.conftest import TicketFactory, World
from tests.helpers import PASSWORD

API = "/api/v1"


def test_refresh_token_cookie_flow(world: World) -> None:
    r = world.client.post(
        f"{API}/auth/login", data={"username": "tech.a@example.org", "password": PASSWORD}
    )
    set_cookie = r.headers["set-cookie"]
    assert "refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    first_cookie = world.client.cookies.get("refresh_token")

    # Refresh without body: the cookie is used and rotated
    r = world.client.post(f"{API}/auth/refresh")
    assert r.status_code == 200
    assert world.client.cookies.get("refresh_token") != first_cookie
    access = r.json()["access_token"]

    # Logout without body: cookie revoked and cleared
    r = world.client.post(f"{API}/auth/logout", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 204
    assert world.client.cookies.get("refresh_token") is None
    assert world.client.post(f"{API}/auth/refresh").status_code == 401


def test_refresh_without_any_token(world: World) -> None:
    world.client.cookies.clear()
    r = world.client.post(f"{API}/auth/refresh")
    assert r.status_code == 401


def test_display_names_in_ticket_and_history(world: World, make_ticket: TicketFactory) -> None:
    ticket = make_ticket(by=world.client_a)
    assert ticket["created_by_name"] == world.client_a.full_name
    history = world.client.get(
        f"{API}/tickets/{ticket['id']}/history", headers=world.headers(world.admin)
    ).json()
    assert history[0]["actor_name"] == world.client_a.full_name


def test_spa_is_served_with_strict_csp(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root></div>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (dist / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("TOP-SECRET")
    settings = Settings(
        secret_key=SecretStr("k" * 40),
        database_url="sqlite://",
        frontend_dist=dist,
        upload_dir=tmp_path / "up",
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as client:
        for path in ["/", "/tickets/123", "/login"]:
            r = client.get(path)
            assert r.status_code == 200
            assert "id=root" in r.text
            assert "script-src 'self'" in r.headers["content-security-policy"]
        assert client.get("/assets/app.js").text == "console.log(1)"
        assert client.get("/favicon.svg").status_code == 200
        for attempt in ["/..%2fsecret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt"]:
            assert "TOP-SECRET" not in client.get(attempt).text
        assert "root" not in client.get("/api/v1/unknown").text
        assert client.get("/api/v1/unknown").status_code == 404
        assert (
            client.get(f"{API}/health").headers["content-security-policy"]
            == "default-src 'none'; frame-ancestors 'none'"
        )
    app.state.engine.dispose()
