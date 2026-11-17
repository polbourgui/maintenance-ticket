"""RBAC: role permissions and per-site isolation."""

from __future__ import annotations

import pytest

from tests.conftest import TicketFactory, World

API = "/api/v1"


def test_unauthenticated_requests_are_rejected(world: World) -> None:
    for method, path in [
        ("GET", "/tickets"),
        ("GET", "/sites"),
        ("GET", "/users/me"),
        ("GET", "/reports/dashboard"),
        ("POST", "/notifications/test"),
    ]:
        r = world.client.request(method, f"{API}{path}")
        assert r.status_code == 401, path
        assert r.headers["www-authenticate"] == "Bearer"


def test_client_can_create_but_not_manage(world: World, make_ticket: TicketFactory) -> None:
    ticket = make_ticket(by=world.client_a)
    h = world.headers(world.client_a)
    tid = ticket["id"]
    assert (
        world.client.put(
            f"{API}/tickets/{tid}/assignment",
            json={"technician_id": str(world.tech_a.id)},
            headers=h,
        ).status_code
        == 403
    )
    assert (
        world.client.patch(f"{API}/tickets/{tid}", json={"title": "Hack"}, headers=h).status_code
        == 403
    )
    assert (
        world.client.post(
            f"{API}/tickets/{tid}/status", json={"status": "blocked", "comment": "x"}, headers=h
        ).status_code
        == 403
    )
    assert world.client.post(f"{API}/tickets/{tid}/archive", headers=h).status_code == 403


def test_client_cannot_create_ticket_on_foreign_site(world: World) -> None:
    r = world.client.post(
        f"{API}/tickets",
        json={
            "site_id": str(world.site_b.id),
            "title": "Intrusion",
            "description": "x",
            "location": {"room": "R"},
        },
        headers=world.headers(world.client_a),
    )
    assert r.status_code == 404


@pytest.mark.parametrize("who", ["tech_b", "client_a"])
def test_site_isolation_hides_foreign_tickets(
    world: World, make_ticket: TicketFactory, who: str
) -> None:
    foreign = make_ticket(site=world.site_b if who == "client_a" else world.site_a)
    user = getattr(world, who)
    h = world.headers(user)
    tid = foreign["id"]
    # 404, not 403: existence is not leaked
    assert world.client.get(f"{API}/tickets/{tid}", headers=h).status_code == 404
    assert world.client.get(f"{API}/tickets/{tid}/history", headers=h).status_code == 404
    assert world.client.get(f"{API}/tickets/{tid}/photos", headers=h).status_code == 404
    assert world.client.get(f"{API}/tickets", headers=h).json()["total"] == 0


def test_listing_is_scoped_by_site(world: World, make_ticket: TicketFactory) -> None:
    make_ticket(site=world.site_a)
    make_ticket(site=world.site_b)
    assert (
        world.client.get(f"{API}/tickets", headers=world.headers(world.admin)).json()["total"] == 2
    )
    assert (
        world.client.get(f"{API}/tickets", headers=world.headers(world.tech_a)).json()["total"] == 1
    )
    sites = world.client.get(f"{API}/sites", headers=world.headers(world.tech_b)).json()
    assert [s["code"] for s in sites["items"]] == ["ERP-B"]
    # Filtering explicitly on a foreign site still returns nothing
    r = world.client.get(
        f"{API}/tickets",
        params={"site_id": str(world.site_b.id)},
        headers=world.headers(world.tech_a),
    ).json()
    assert r["total"] == 0


def test_only_assigned_technician_changes_status(world: World, make_ticket: TicketFactory) -> None:
    tid = make_ticket()["id"]
    world.client.put(
        f"{API}/tickets/{tid}/assignment",
        json={"technician_id": str(world.tech_a.id)},
        headers=world.headers(world.admin),
    )
    r = world.client.post(
        f"{API}/tickets/{tid}/status",
        json={"status": "in_progress"},
        headers=world.headers(world.tech_a2),
    )
    assert r.status_code == 403
    r = world.client.post(
        f"{API}/tickets/{tid}/status",
        json={"status": "in_progress"},
        headers=world.headers(world.tech_a),
    )
    assert r.status_code == 200


def test_technician_cannot_assign_or_archive(world: World, make_ticket: TicketFactory) -> None:
    tid = make_ticket()["id"]
    h = world.headers(world.tech_a)
    assert (
        world.client.put(
            f"{API}/tickets/{tid}/assignment",
            json={"technician_id": str(world.tech_a.id)},
            headers=h,
        ).status_code
        == 403
    )
    assert world.client.post(f"{API}/tickets/{tid}/archive", headers=h).status_code == 403


@pytest.mark.parametrize("who", ["tech_a", "client_a"])
def test_admin_only_endpoints(world: World, who: str) -> None:
    h = world.headers(getattr(world, who))
    site = {
        "code": "NEW",
        "name": "Nouveau",
        "address": "x rue",
        "postal_code": "75000",
        "city": "Paris",
        "erp_type": "M",
        "erp_category": 4,
    }
    user = {
        "email": "x@example.org",
        "full_name": "X",
        "password": "Str0ng-Passw0rd!",
        "role": "admin",
    }
    assert world.client.post(f"{API}/sites", json=site, headers=h).status_code == 403
    assert world.client.post(f"{API}/users", json=user, headers=h).status_code == 403
    assert world.client.get(f"{API}/users", headers=h).status_code == 403
    assert (
        world.client.post(
            f"{API}/providers", json={"company_name": "P", "email": "p@example.org"}, headers=h
        ).status_code
        == 403
    )
    assert world.client.post(f"{API}/notifications/test", headers=h).status_code == 403
    assert (
        world.client.post(
            f"{API}/sites/{world.site_a.id}/members",
            json={"user_id": str(world.tech_b.id)},
            headers=h,
        ).status_code
        == 403
    )


def test_providers_visible_to_technicians_not_clients(world: World) -> None:
    assert (
        world.client.get(f"{API}/providers", headers=world.headers(world.tech_a)).status_code == 200
    )
    assert (
        world.client.get(f"{API}/providers", headers=world.headers(world.client_a)).status_code
        == 403
    )


def test_admin_user_and_site_management(world: World) -> None:
    h = world.headers(world.admin)
    r = world.client.post(
        f"{API}/sites",
        json={
            "code": "erp-c",
            "name": "Piscine C",
            "address": "3 rue C",
            "postal_code": "33000",
            "city": "Bordeaux",
            "erp_type": "x",
            "erp_category": 2,
        },
        headers=h,
    )
    assert r.status_code == 201
    site_c = r.json()
    assert site_c["code"] == "ERP-C"
    assert (
        world.client.post(
            f"{API}/sites",
            json={
                "code": "ERP-C",
                "name": "Dup",
                "address": "3 rue C",
                "postal_code": "33000",
                "city": "Bordeaux",
                "erp_type": "X",
                "erp_category": 2,
            },
            headers=h,
        ).status_code
        == 409
    )

    r = world.client.post(
        f"{API}/users",
        json={
            "email": "new.tech@example.org",
            "full_name": "New Tech",
            "password": "weak",
            "role": "technician",
        },
        headers=h,
    )
    assert r.status_code == 422  # password policy
    r = world.client.post(
        f"{API}/users",
        json={
            "email": "new.tech@example.org",
            "full_name": "New Tech",
            "password": "Sup3r-Secret-Pwd",
            "role": "technician",
            "site_ids": [site_c["id"]],
        },
        headers=h,
    )
    assert r.status_code == 201
    new_id = r.json()["id"]
    assert r.json()["site_ids"] == [site_c["id"]]
    assert "hashed_password" not in r.json()

    r = world.client.post(
        f"{API}/sites/{world.site_a.id}/members", json={"user_id": new_id}, headers=h
    )
    assert r.status_code == 204
    user = world.client.get(f"{API}/users/{new_id}", headers=h).json()
    assert set(user["site_ids"]) == {site_c["id"], str(world.site_a.id)}
    r = world.client.delete(f"{API}/sites/{world.site_a.id}/members/{new_id}", headers=h)
    assert r.status_code == 204

    # Admin cannot demote themselves
    r = world.client.patch(f"{API}/users/{world.admin.id}", json={"role": "client"}, headers=h)
    assert r.status_code == 422


def test_role_change_revokes_existing_tokens(world: World) -> None:
    tech_headers = world.headers(world.tech_a)
    assert world.client.get(f"{API}/users/me", headers=tech_headers).status_code == 200
    r = world.client.patch(
        f"{API}/users/{world.tech_a.id}",
        json={"role": "client"},
        headers=world.headers(world.admin),
    )
    assert r.status_code == 200
    assert world.client.get(f"{API}/users/me", headers=tech_headers).status_code == 401


def test_deactivated_user_loses_access(world: World) -> None:
    tech_headers = world.headers(world.tech_a)
    world.client.patch(
        f"{API}/users/{world.tech_a.id}",
        json={"is_active": False},
        headers=world.headers(world.admin),
    )
    assert world.client.get(f"{API}/users/me", headers=tech_headers).status_code == 401
    r = world.client.post(
        f"{API}/auth/login", data={"username": world.tech_a.email, "password": "Str0ng-Passw0rd!"}
    )
    assert r.status_code == 401
