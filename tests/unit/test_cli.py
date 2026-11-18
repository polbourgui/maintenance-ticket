from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app import cli
from app.core.config import get_settings
from app.core.security import verify_password
from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory
from app.models import RefreshToken, User

EMAIL = "admin@example.org"
FIRST = "Premier-Passw0rd!"
SECOND = "Nouveau-Passw0rd!"


@pytest.fixture
def db_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = f"sqlite:///{tmp_path / 'cli.db'}"
    monkeypatch.setenv("APP_DATABASE_URL", url)
    monkeypatch.setenv("APP_SECRET_KEY", "cli-test-secret-" + "x" * 32)
    monkeypatch.delenv("APP_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("APP_NEW_PASSWORD", raising=False)
    get_settings.cache_clear()
    engine = create_db_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    yield url
    get_settings.cache_clear()


def _typed(monkeypatch: pytest.MonkeyPatch, *answers: str) -> None:
    replies = iter(answers)
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": next(replies))


def _user(url: str) -> User:
    engine = create_db_engine(url)
    with create_session_factory(engine)() as session:
        user = session.scalars(select(User)).one()
    engine.dispose()
    return user


def test_create_admin_then_reset_password(
    db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _typed(monkeypatch, FIRST, FIRST)
    assert cli.main(["create-admin", "--email", EMAIL, "--full-name", "Admin"]) == 0
    assert verify_password(_user(db_url).hashed_password, FIRST)

    # Creating it twice fails before asking for a password, and points to reset-password
    assert cli.main(["create-admin", "--email", EMAIL, "--full-name", "Admin"]) == 1
    assert "reset-password" in capsys.readouterr().err

    _typed(monkeypatch, SECOND, SECOND)
    assert cli.main(["reset-password", "--email", "ADMIN@example.org"]) == 0
    user = _user(db_url)
    assert verify_password(user.hashed_password, SECOND)
    assert not verify_password(user.hashed_password, FIRST)
    assert user.token_version == 1  # existing access tokens are invalidated
    assert "sessions de ce compte ont été fermées" in capsys.readouterr().out


def test_reset_revokes_refresh_tokens(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _typed(monkeypatch, FIRST, FIRST)
    cli.main(["create-admin", "--email", EMAIL, "--full-name", "Admin"])
    engine = create_db_engine(db_url)
    factory = create_session_factory(engine)
    with factory() as session:
        user = session.scalars(select(User)).one()
        session.add(
            RefreshToken(
                user_id=user.id,
                token_hash="h" * 64,
                family_id=uuid.uuid4(),
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        session.commit()

    monkeypatch.setenv("APP_NEW_PASSWORD", SECOND)
    assert cli.main(["reset-password", "--email", EMAIL]) == 0
    with factory() as session:
        assert session.scalars(select(RefreshToken)).one().revoked_at is not None
    engine.dispose()


def test_reset_rejects_mismatch_weak_password_and_unknown_user(
    db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _typed(monkeypatch, FIRST, FIRST)
    cli.main(["create-admin", "--email", EMAIL, "--full-name", "Admin"])

    _typed(monkeypatch, SECOND, "Autre-Passw0rd!")
    assert cli.main(["reset-password", "--email", EMAIL]) == 1
    assert "ne correspondent pas" in capsys.readouterr().err

    _typed(monkeypatch, "court", "court")
    assert cli.main(["reset-password", "--email", EMAIL]) == 1
    assert "12" in capsys.readouterr().err

    assert verify_password(_user(db_url).hashed_password, FIRST)  # unchanged

    assert cli.main(["reset-password", "--email", "nobody@example.org"]) == 1
    assert "aucun utilisateur" in capsys.readouterr().err
