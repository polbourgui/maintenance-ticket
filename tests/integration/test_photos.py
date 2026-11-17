from __future__ import annotations

import hashlib

import httpx

from tests.conftest import TicketFactory, World
from tests.helpers import make_jpeg, make_png

API = "/api/v1"


def _upload(
    world: World,
    ticket_id: object,
    user: object,
    data: bytes,
    kind: str = "before",
    filename: str = "photo.jpg",
    content_type: str = "image/jpeg",
) -> httpx.Response:
    response: httpx.Response = world.client.post(
        f"{API}/tickets/{ticket_id}/photos",
        data={"kind": kind},
        files={"file": (filename, data, content_type)},
        headers=world.headers(user),  # type: ignore[arg-type]
    )
    return response


def test_before_after_photos_with_metadata_stripped(
    world: World, make_ticket: TicketFactory
) -> None:
    tid = make_ticket()["id"]
    r = _upload(world, tid, world.tech_a, make_jpeg(), kind="before")
    assert r.status_code == 201, r.text
    before = r.json()
    assert before["kind"] == "before"
    assert before["content_type"] == "image/jpeg"

    r = _upload(
        world,
        tid,
        world.tech_a,
        make_png(),
        kind="after",
        filename="x.png",
        content_type="image/png",
    )
    assert r.status_code == 201
    after = r.json()

    listing = world.client.get(
        f"{API}/tickets/{tid}/photos", headers=world.headers(world.client_a)
    ).json()
    assert [p["kind"] for p in listing] == ["before", "after"]

    content = world.client.get(
        f"{API}/tickets/{tid}/photos/{before['id']}", headers=world.headers(world.client_a)
    )
    assert content.status_code == 200
    assert content.headers["content-type"] == "image/jpeg"
    assert b"GPS" not in content.content
    assert b"Jean Dupont" not in content.content
    assert content.content.startswith(b"\xff\xd8")
    assert content.content.endswith(b"\xff\xd9")
    assert hashlib.sha256(content.content).hexdigest() == before["sha256"]

    png = world.client.get(
        f"{API}/tickets/{tid}/photos/{after['id']}", headers=world.headers(world.admin)
    )
    assert b"Jean Dupont" not in png.content
    assert b"IDAT" in png.content

    history = world.client.get(
        f"{API}/tickets/{tid}/history", headers=world.headers(world.admin)
    ).json()
    assert [e["details"].get("kind") for e in history if e["event_type"] == "photo_added"] == [
        "before",
        "after",
    ]


def test_rejects_non_images_regardless_of_declared_type(
    world: World, make_ticket: TicketFactory
) -> None:
    tid = make_ticket()["id"]
    r = _upload(world, tid, world.tech_a, b"<svg onload=alert(1)>", filename="x.jpg")
    assert r.status_code == 422
    r = _upload(world, tid, world.tech_a, b"%PDF-1.7 ...", filename="x.jpg")
    assert r.status_code == 422


def test_rejects_oversized_upload(world: World, make_ticket: TicketFactory) -> None:
    tid = make_ticket()["id"]
    big = make_jpeg()[:-2] + b"\x00" * (70 * 1024) + b"\xff\xd9"
    r = _upload(world, tid, world.tech_a, big)
    assert r.status_code == 413


def test_photo_permissions(world: World, make_ticket: TicketFactory) -> None:
    tid = make_ticket()["id"]
    assert _upload(world, tid, world.client_a, make_jpeg()).status_code == 403
    assert _upload(world, tid, world.tech_b, make_jpeg()).status_code == 404  # other site
    photo = _upload(world, tid, world.tech_a, make_jpeg()).json()
    r = world.client.get(
        f"{API}/tickets/{tid}/photos/{photo['id']}", headers=world.headers(world.tech_b)
    )
    assert r.status_code == 404

    # A photo id can't be read through another (accessible) ticket
    other = make_ticket()["id"]
    r = world.client.get(
        f"{API}/tickets/{other}/photos/{photo['id']}", headers=world.headers(world.admin)
    )
    assert r.status_code == 404


def test_invalid_kind(world: World, make_ticket: TicketFactory) -> None:
    tid = make_ticket()["id"]
    assert _upload(world, tid, world.tech_a, make_jpeg(), kind="during").status_code == 422
