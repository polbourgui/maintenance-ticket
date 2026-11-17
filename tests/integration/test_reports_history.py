from __future__ import annotations

from tests.conftest import TicketFactory, World

API = "/api/v1"


def _complete(world: World, tid: object) -> None:
    admin = world.headers(world.admin)
    world.client.put(
        f"{API}/tickets/{tid}/assignment",
        json={"technician_id": str(world.tech_a.id)},
        headers=admin,
    )
    for status in ("in_progress", "done"):
        r = world.client.post(f"{API}/tickets/{tid}/status", json={"status": status}, headers=admin)
        assert r.status_code == 200


def test_dashboard_statistics_per_site(world: World, make_ticket: TicketFactory) -> None:
    t1 = make_ticket(priority="critical")
    make_ticket(priority="low")
    t3 = make_ticket()
    make_ticket(site=world.site_b)
    _complete(world, t3["id"])
    world.client.post(f"{API}/tickets/{t3['id']}/archive", headers=world.headers(world.admin))
    world.client.put(
        f"{API}/tickets/{t1['id']}/assignment",
        json={"technician_id": str(world.tech_a.id)},
        headers=world.headers(world.admin),
    )
    world.client.post(
        f"{API}/tickets/{t1['id']}/status",
        json={"status": "blocked", "comment": "attente"},
        headers=world.headers(world.admin),
    )

    r = world.client.get(f"{API}/reports/dashboard", headers=world.headers(world.admin))
    assert r.status_code == 200
    report = r.json()
    assert report["totals"] == {"todo": 2, "in_progress": 0, "blocked": 1, "done": 1}
    site_a = next(s for s in report["sites"] if s["site_code"] == "ERP-A")
    assert site_a["total"] == 3
    assert site_a["open"] == 2
    assert site_a["archived"] == 1
    assert site_a["by_status"]["blocked"] == 1
    assert site_a["open_by_priority"] == {"low": 1, "medium": 0, "high": 0, "critical": 1}
    assert site_a["avg_resolution_hours"] is not None

    # Technician of site B only sees site B
    r = world.client.get(f"{API}/reports/dashboard", headers=world.headers(world.tech_b)).json()
    assert [s["site_code"] for s in r["sites"]] == ["ERP-B"]
    assert (
        world.client.get(
            f"{API}/reports/sites/{world.site_a.id}", headers=world.headers(world.tech_b)
        ).status_code
        == 404
    )
    r = world.client.get(
        f"{API}/reports/sites/{world.site_a.id}", headers=world.headers(world.client_a)
    )
    assert r.status_code == 200
    assert r.json()["total"] == 3


def test_site_history_includes_archived_tickets(world: World, make_ticket: TicketFactory) -> None:
    t = make_ticket()
    _complete(world, t["id"])
    world.client.post(f"{API}/tickets/{t['id']}/archive", headers=world.headers(world.admin))
    make_ticket(site=world.site_b)

    r = world.client.get(
        f"{API}/sites/{world.site_a.id}/history", headers=world.headers(world.client_a)
    )
    assert r.status_code == 200
    page = r.json()
    assert page["total"] == 5  # created, assigned, 2 status changes, archived
    assert {e["ticket_id"] for e in page["items"]} == {t["id"]}
    assert page["items"][0]["event_type"] == "archived"  # most recent first

    assert (
        world.client.get(
            f"{API}/sites/{world.site_b.id}/history", headers=world.headers(world.client_a)
        ).status_code
        == 404
    )
