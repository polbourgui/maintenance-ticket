from __future__ import annotations

import uuid

from tests.conftest import TicketFactory, World

API = "/api/v1"


def test_provider_crud(world: World) -> None:
    h = world.headers(world.admin)
    r = world.client.post(
        f"{API}/providers",
        json={
            "company_name": "Sécurité Incendie SARL",
            "contact_name": "M. Martin",
            "email": "Contact@SSI.example",
            "phone": "+33 1 23 45 67 89",
            "specialty": "SSI",
        },
        headers=h,
    )
    assert r.status_code == 201
    provider = r.json()
    assert provider["email"] == "contact@ssi.example"

    r = world.client.patch(
        f"{API}/providers/{provider['id']}", json={"is_active": False}, headers=h
    )
    assert r.json()["is_active"] is False
    active = world.client.get(f"{API}/providers", headers=h).json()
    assert provider["id"] not in [p["id"] for p in active["items"]]
    every = world.client.get(f"{API}/providers", params={"active_only": False}, headers=h).json()
    assert provider["id"] in [p["id"] for p in every["items"]]
    assert (
        world.client.patch(
            f"{API}/providers/{uuid.uuid4()}", json={"is_active": True}, headers=h
        ).status_code
        == 404
    )


def test_inactive_provider_cannot_be_assigned(world: World, make_ticket: TicketFactory) -> None:
    h = world.headers(world.admin)
    world.client.patch(f"{API}/providers/{world.provider.id}", json={"is_active": False}, headers=h)
    tid = make_ticket()["id"]
    r = world.client.put(
        f"{API}/tickets/{tid}/assignment", json={"provider_id": str(world.provider.id)}, headers=h
    )
    assert r.status_code == 422
    r = world.client.put(
        f"{API}/tickets/{tid}/assignment", json={"provider_id": str(uuid.uuid4())}, headers=h
    )
    assert r.status_code == 404


def test_site_update_and_inactive_site(world: World) -> None:
    h = world.headers(world.admin)
    r = world.client.patch(
        f"{API}/sites/{world.site_a.id}", json={"erp_category": 1, "is_active": False}, headers=h
    )
    assert r.status_code == 200
    assert r.json()["erp_category"] == 1
    assert (
        world.client.patch(
            f"{API}/sites/{world.site_a.id}", json={"erp_category": 6}, headers=h
        ).status_code
        == 422
    )
    r = world.client.post(
        f"{API}/tickets",
        json={
            "site_id": str(world.site_a.id),
            "title": "Fuite",
            "description": "x",
            "location": {"room": "WC"},
        },
        headers=h,
    )
    assert r.status_code == 422
    assert "inactive" in r.json()["detail"]
    assert world.client.get(f"{API}/sites/{uuid.uuid4()}", headers=h).status_code == 404
    got = world.client.get(f"{API}/sites/{world.site_a.id}", headers=world.headers(world.client_a))
    assert got.status_code == 200


def test_membership_errors(world: World) -> None:
    h = world.headers(world.admin)
    r = world.client.post(
        f"{API}/sites/{world.site_a.id}/members", json={"user_id": str(uuid.uuid4())}, headers=h
    )
    assert r.status_code == 404
    r = world.client.post(
        f"{API}/users",
        json={
            "email": "x@example.org",
            "full_name": "X",
            "password": "Sup3r-Secret-Pwd",
            "role": "client",
            "site_ids": [str(uuid.uuid4())],
        },
        headers=h,
    )
    assert r.status_code == 404
    r = world.client.post(
        f"{API}/users",
        json={
            "email": "tech.a@example.org",
            "full_name": "Dup",
            "password": "Sup3r-Secret-Pwd",
            "role": "client",
        },
        headers=h,
    )
    assert r.status_code == 409


def test_user_listing_filters(world: World) -> None:
    h = world.headers(world.admin)
    r = world.client.get(f"{API}/users", params={"role": "technician"}, headers=h).json()
    assert r["total"] == 3
    r = world.client.get(f"{API}/users", params={"site_id": str(world.site_b.id)}, headers=h).json()
    assert [u["email"] for u in r["items"]] == ["tech.b@example.org"]
