from __future__ import annotations

from app.notifications import InMemoryNotifier
from tests.conftest import TicketFactory, World
from tests.helpers import PASSWORD

API = "/api/v1"


def test_personal_data_export(world: World, make_ticket: TicketFactory) -> None:
    make_ticket(by=world.client_a)
    r = world.client.get(f"{API}/users/me/export", headers=world.headers(world.client_a))
    assert r.status_code == 200
    export = r.json()
    assert export["profile"]["email"] == "client.a@example.org"
    assert len(export["tickets_created"]) == 1
    assert export["ticket_events"][0]["event_type"] == "created"
    assert export["active_sessions"] >= 1
    assert "hashed_password" not in r.text


def test_self_erasure_anonymizes_but_keeps_records(
    world: World, make_ticket: TicketFactory
) -> None:
    ticket = make_ticket(by=world.client_a)
    r = world.client.delete(f"{API}/users/me", headers=world.headers(world.client_a))
    assert r.status_code == 204

    # Login impossible, tokens revoked
    login = world.client.post(
        f"{API}/auth/login", data={"username": "client.a@example.org", "password": PASSWORD}
    )
    assert login.status_code == 401
    assert (
        world.client.get(f"{API}/users/me", headers=world.headers(world.client_a)).status_code
        == 401
    )

    # Maintenance record retained, linked to an opaque, anonymized identity
    admin = world.headers(world.admin)
    t = world.client.get(f"{API}/tickets/{ticket['id']}", headers=admin).json()
    assert t["created_by_id"] == str(world.client_a.id)
    user = world.client.get(f"{API}/users/{world.client_a.id}", headers=admin).json()
    assert user["full_name"] == "Utilisateur supprimé"
    assert user["email"].endswith("@anonymized.invalid")
    assert user["phone"] is None
    assert user["is_active"] is False
    assert user["site_ids"] == []


def test_anonymized_user_receives_no_notifications(
    world: World, make_ticket: TicketFactory, notifier: InMemoryNotifier
) -> None:
    ticket = make_ticket(by=world.client_a)
    admin = world.headers(world.admin)
    world.client.post(f"{API}/users/{world.client_a.id}/anonymize", headers=admin)
    world.client.put(
        f"{API}/tickets/{ticket['id']}/assignment",
        json={"technician_id": str(world.tech_a.id)},
        headers=admin,
    )
    world.client.post(
        f"{API}/tickets/{ticket['id']}/status", json={"status": "in_progress"}, headers=admin
    )
    assert notifier.sent[-1].email_recipients == ("tech.a@example.org",)


def test_users_cannot_anonymize_others(world: World) -> None:
    r = world.client.post(
        f"{API}/users/{world.tech_a.id}/anonymize", headers=world.headers(world.client_a)
    )
    assert r.status_code == 403


def test_last_admin_cannot_be_anonymized(world: World) -> None:
    r = world.client.delete(f"{API}/users/me", headers=world.headers(world.admin))
    assert r.status_code == 422
