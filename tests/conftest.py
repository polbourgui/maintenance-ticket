from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.db.base import Base
from app.main import create_app
from app.models import Provider, Role, Site, User
from app.notifications import InMemoryNotifier, NotificationDispatcher
from tests.helpers import PASSWORD

_PASSWORD_HASH = hash_password(PASSWORD)  # computed once: Argon2 is slow by design


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        secret_key=SecretStr("test-secret-key-" + "x" * 32),
        environment="test",
        database_url="sqlite://",
        upload_dir=tmp_path / "uploads",
        login_max_attempts=3,
        max_upload_bytes=64 * 1024,
    )


@pytest.fixture
def notifier() -> InMemoryNotifier:
    return InMemoryNotifier()


@pytest.fixture
def app(settings: Settings, notifier: InMemoryNotifier) -> Iterator[FastAPI]:
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    application.state.dispatcher = NotificationDispatcher([notifier])
    yield application
    Base.metadata.drop_all(application.state.engine)
    application.state.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db(app: FastAPI) -> Iterator[Session]:
    session: Session = app.state.session_factory()
    yield session
    session.close()


@dataclass
class World:
    """A small multi-site dataset: site A and site B, one user of each role per site."""

    db: Session
    client: TestClient
    site_a: Site
    site_b: Site
    admin: User
    tech_a: User
    tech_a2: User
    tech_b: User
    client_a: User
    provider: Provider
    _headers: dict[str, dict[str, str]] = field(default_factory=dict)

    def headers(self, user: User) -> dict[str, str]:
        if user.email not in self._headers:
            self._headers[user.email] = auth_headers(self.client, user.email)
        return self._headers[user.email]

    def create_user(self, email: str, role: Role, sites: list[Site]) -> User:
        return create_user(self.db, email, role, sites)


def create_user(db: Session, email: str, role: Role, sites: list[Site]) -> User:
    user = User(
        email=email,
        full_name=email.split("@", maxsplit=1)[0].title(),
        role=role,
        hashed_password=_PASSWORD_HASH,
        is_active=True,
        token_version=0,
    )
    user.sites = list(sites)
    db.add(user)
    db.commit()
    return user


def auth_headers(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def world(db: Session, client: TestClient) -> World:
    site_a = Site(
        code="ERP-A",
        name="Médiathèque A",
        address="1 rue A",
        postal_code="75001",
        city="Paris",
        erp_type="S",
        erp_category=3,
        is_active=True,
    )
    site_b = Site(
        code="ERP-B",
        name="Gymnase B",
        address="2 rue B",
        postal_code="69001",
        city="Lyon",
        erp_type="X",
        erp_category=2,
        is_active=True,
    )
    provider = Provider(
        company_name="Ascenseurs SA", email="sav@ascenseurs.example", is_active=True
    )
    db.add_all([site_a, site_b, provider])
    db.commit()
    w = World(
        db=db,
        client=client,
        site_a=site_a,
        site_b=site_b,
        admin=create_user(db, "admin@example.org", Role.ADMIN, []),
        tech_a=create_user(db, "tech.a@example.org", Role.TECHNICIAN, [site_a]),
        tech_a2=create_user(db, "tech.a2@example.org", Role.TECHNICIAN, [site_a]),
        tech_b=create_user(db, "tech.b@example.org", Role.TECHNICIAN, [site_b]),
        client_a=create_user(db, "client.a@example.org", Role.CLIENT, [site_a]),
        provider=provider,
    )
    return w


TicketFactory = Callable[..., dict[str, object]]


@pytest.fixture
def make_ticket(world: World) -> TicketFactory:
    def _make(
        by: User | None = None, site: Site | None = None, **overrides: object
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "site_id": str((site or world.site_a).id),
            "title": "Alarme incendie en défaut",
            "description": "Le SSI affiche un défaut sur la zone 3.",
            "priority": "high",
            "location": {"building": "Bât. principal", "floor": "R+1", "room": "Local SSI"},
        } | overrides
        response = world.client.post(
            "/api/v1/tickets", json=payload, headers=world.headers(by or world.admin)
        )
        assert response.status_code == 201, response.text
        body: dict[str, object] = response.json()
        return body

    return _make
