"""Full ticket lifecycle: creation -> assignment -> workflow -> archive, with notifications."""

from __future__ import annotations

import httpx

from app.notifications import InMemoryNotifier
from tests.conftest import TicketFactory, World

API = "/api/v1"


def _status(
    world: World, ticket_id: object, status: str, user: object, comment: str | None = None
) -> httpx.Response:
    body: dict[str, object] = {"status": status}
    if comment is not None:
        body["comment"] = comment
    response: httpx.Response = world.client.post(
        f"{API}/tickets/{ticket_id}/status",
        json=body,
        headers=world.headers(user),  # type: ignore[arg-type]
    )
    return response


def test_create_assign_and_notify(
    world: World, make_ticket: TicketFactory, notifier: InMemoryNotifier
) -> None:
    """DoD: a ticket can be created, assigned and triggers a notification."""
    ticket = make_ticket(by=world.client_a)
    assert ticket["status"] == "todo"
    assert ticket["assignee"] is None
    assert ticket["location"]["room"] == "Local SSI"  # type: ignore[index]
    assert ticket["created_by_id"] == str(world.client_a.id)
    assert notifier.sent == []

    response = world.client.put(
        f"{API}/tickets/{ticket['id']}/assignment",
        json={"technician_id": str(world.tech_a.id)},
        headers=world.headers(world.admin),
    )
    assert response.status_code == 200, response.text
    assert response.json()["assignee"] == {
        "type": "technician",
        "id": str(world.tech_a.id),
        "display_name": world.tech_a.full_name,
    }

    assert len(notifier.sent) == 1
    sent = notifier.sent[0]
    assert sent.event == "ticket.assigned"
    assert sent.email_recipients == ("tech.a@example.org",)
    assert "ERP-A" in sent.subject
    # Full location, French priority and the description so the assignee knows what to do
    assert "Localisation : Bât. principal · R+1 · Local SSI\n" in sent.body
    assert "Priorité : Haute\n" in sent.body
    assert "Le SSI affiche un défaut sur la zone 3." in sent.body
    assert "priorité haute" in sent.summary
    # GDPR: the log summary never contains personal data
    assert "@" not in sent.summary
    assert world.tech_a.full_name not in sent.summary


def test_full_workflow_and_history(
    world: World, make_ticket: TicketFactory, notifier: InMemoryNotifier
) -> None:
    ticket = make_ticket(by=world.client_a)
    tid = ticket["id"]

    # Cannot start an unassigned ticket
    r = _status(world, tid, "in_progress", world.admin)
    assert r.status_code == 422
    assert "assigned" in r.json()["detail"]

    world.client.put(
        f"{API}/tickets/{tid}/assignment",
        json={"technician_id": str(world.tech_a.id)},
        headers=world.headers(world.admin),
    )

    r = _status(world, tid, "in_progress", world.tech_a)
    assert r.status_code == 200
    assert r.json()["started_at"] is not None

    # Blocking requires a reason
    assert _status(world, tid, "blocked", world.tech_a).status_code == 422
    r = _status(world, tid, "blocked", world.tech_a, comment="Pièce détachée en commande")
    assert r.status_code == 200
    assert r.json()["status"] == "blocked"

    # blocked -> done is not an allowed transition
    assert _status(world, tid, "done", world.tech_a).status_code == 422

    assert _status(world, tid, "in_progress", world.tech_a).status_code == 200
    r = _status(world, tid, "done", world.tech_a, comment="Détecteur remplacé")
    assert r.status_code == 200
    assert r.json()["closed_at"] is not None

    # Status notifications go to the creator and the assignee
    status_events = [n for n in notifier.sent if n.event == "ticket.status_changed"]
    assert len(status_events) == 4
    assert set(status_events[-1].email_recipients) == {"client.a@example.org", "tech.a@example.org"}
    assert "En cours → Terminé" in status_events[-1].subject
    assert "Localisation : Bât. principal · R+1 · Local SSI" in status_events[-1].body
    assert "Priorité : Haute" in status_events[-1].body
    assert "Commentaire : Détecteur remplacé" in status_events[-1].body

    # Archive
    r = world.client.post(f"{API}/tickets/{tid}/archive", headers=world.headers(world.admin))
    assert r.status_code == 200
    assert r.json()["archived_at"] is not None

    # Archived tickets are read-only and hidden from default listings
    assert _status(world, tid, "in_progress", world.admin).status_code == 422
    r = world.client.patch(
        f"{API}/tickets/{tid}", json={"title": "Nouveau titre"}, headers=world.headers(world.admin)
    )
    assert r.status_code == 422
    listing = world.client.get(f"{API}/tickets", headers=world.headers(world.admin)).json()
    assert listing["total"] == 0
    listing = world.client.get(
        f"{API}/tickets", params={"include_archived": True}, headers=world.headers(world.admin)
    ).json()
    assert listing["total"] == 1

    history = world.client.get(
        f"{API}/tickets/{tid}/history", headers=world.headers(world.client_a)
    )
    assert history.status_code == 200
    types = [e["event_type"] for e in history.json()]
    assert types == [
        "created",
        "assigned",
        "status_changed",
        "status_changed",
        "status_changed",
        "status_changed",
        "archived",
    ]
    blocked = history.json()[3]
    assert blocked["from_status"] == "in_progress"
    assert blocked["to_status"] == "blocked"
    assert blocked["comment"] == "Pièce détachée en commande"


def test_assign_to_external_provider_notifies_provider(
    world: World, make_ticket: TicketFactory, notifier: InMemoryNotifier
) -> None:
    ticket = make_ticket()
    r = world.client.put(
        f"{API}/tickets/{ticket['id']}/assignment",
        json={"provider_id": str(world.provider.id)},
        headers=world.headers(world.admin),
    )
    assert r.status_code == 200
    assert r.json()["assignee"]["type"] == "provider"
    assert r.json()["assignee"]["display_name"] == "Ascenseurs SA"
    assert notifier.sent[-1].email_recipients == ("sav@ascenseurs.example",)
    assert "prestataire externe" in notifier.sent[-1].summary


def test_assignment_validation(world: World, make_ticket: TicketFactory) -> None:
    ticket = make_ticket()
    url = f"{API}/tickets/{ticket['id']}/assignment"
    admin = world.headers(world.admin)

    both = {"technician_id": str(world.tech_a.id), "provider_id": str(world.provider.id)}
    assert world.client.put(url, json=both, headers=admin).status_code == 422
    # Technician from another site
    r = world.client.put(url, json={"technician_id": str(world.tech_b.id)}, headers=admin)
    assert r.status_code == 422
    # A client is not a technician
    r = world.client.put(url, json={"technician_id": str(world.client_a.id)}, headers=admin)
    assert r.status_code == 404
    # Unassign
    world.client.put(url, json={"technician_id": str(world.tech_a.id)}, headers=admin)
    r = world.client.put(url, json={}, headers=admin)
    assert r.status_code == 200
    assert r.json()["assignee"] is None


def test_reopen_is_admin_only(world: World, make_ticket: TicketFactory) -> None:
    tid = make_ticket()["id"]
    world.client.put(
        f"{API}/tickets/{tid}/assignment",
        json={"technician_id": str(world.tech_a.id)},
        headers=world.headers(world.admin),
    )
    _status(world, tid, "in_progress", world.tech_a)
    _status(world, tid, "done", world.tech_a)

    assert _status(world, tid, "in_progress", world.tech_a).status_code == 403
    r = _status(world, tid, "in_progress", world.admin, comment="Défaut réapparu")
    assert r.status_code == 200
    assert r.json()["closed_at"] is None


def test_update_ticket_records_changed_fields(world: World, make_ticket: TicketFactory) -> None:
    tid = make_ticket()["id"]
    r = world.client.patch(
        f"{API}/tickets/{tid}",
        json={"priority": "critical", "location": {"room": "Chaufferie"}},
        headers=world.headers(world.tech_a),
    )
    assert r.status_code == 200
    assert r.json()["priority"] == "critical"
    assert r.json()["location"] == {
        "building": None,
        "floor": None,
        "room": "Chaufferie",
        "details": None,
    }
    history = world.client.get(
        f"{API}/tickets/{tid}/history", headers=world.headers(world.admin)
    ).json()
    assert history[-1]["event_type"] == "updated"
    assert "priority" in history[-1]["details"]["fields"]


def test_ticket_input_validation(world: World) -> None:
    headers = world.headers(world.admin)
    base = {
        "site_id": str(world.site_a.id),
        "title": "OK title",
        "description": "d",
        "location": {"room": "R1"},
    }
    assert (
        world.client.post(f"{API}/tickets", json=base | {"title": "x"}, headers=headers).status_code
        == 422
    )
    assert (
        world.client.post(
            f"{API}/tickets", json=base | {"priority": "urgent"}, headers=headers
        ).status_code
        == 422
    )
    # Mass-assignment protection: unknown fields (e.g. status) are rejected
    assert (
        world.client.post(
            f"{API}/tickets", json=base | {"status": "done"}, headers=headers
        ).status_code
        == 422
    )
    assert world.client.post(f"{API}/tickets", json=base, headers=headers).status_code == 201


def test_filters(world: World, make_ticket: TicketFactory) -> None:
    make_ticket(priority="low")
    make_ticket(priority="critical")
    make_ticket(site=world.site_b)
    headers = world.headers(world.admin)
    r = world.client.get(f"{API}/tickets", params={"priority": "critical"}, headers=headers).json()
    assert r["total"] == 1
    r = world.client.get(
        f"{API}/tickets", params={"site_id": str(world.site_b.id)}, headers=headers
    ).json()
    assert r["total"] == 1
    r = world.client.get(
        f"{API}/tickets", params={"status": "todo", "limit": 2}, headers=headers
    ).json()
    assert r["total"] == 3
    assert len(r["items"]) == 2
