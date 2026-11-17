from __future__ import annotations

from app.notifications import InMemoryNotifier
from tests.conftest import World

API = "/api/v1"


def test_health(world: World) -> None:
    assert world.client.get(f"{API}/health").json() == {"status": "ok"}


def test_notification_self_test(world: World, notifier: InMemoryNotifier) -> None:
    r = world.client.post(f"{API}/notifications/test", headers=world.headers(world.admin))
    assert r.status_code == 200
    assert r.json() == [{"channel": "memory", "delivered": True, "detail": ""}]
    assert notifier.sent[0].event == "notification.test"
    assert notifier.sent[0].email_recipients == ("admin@example.org",)


def test_security_headers(world: World) -> None:
    r = world.client.get(f"{API}/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["content-security-policy"].startswith("default-src 'none'")
    assert r.headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in r.headers  # only in production


def test_openapi_documents_all_features(world: World) -> None:
    spec = world.client.get("/openapi.json").json()
    paths = spec["paths"]
    for path in [
        "/api/v1/tickets",
        "/api/v1/tickets/{ticket_id}/assignment",
        "/api/v1/tickets/{ticket_id}/status",
        "/api/v1/tickets/{ticket_id}/photos",
        "/api/v1/reports/dashboard",
        "/api/v1/sites/{site_id}/history",
        "/api/v1/users/me/export",
        "/api/v1/notifications/test",
    ]:
        assert path in paths
    assert "OAuth2PasswordBearer" in spec["components"]["securitySchemes"]
