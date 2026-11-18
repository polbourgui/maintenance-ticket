"""Administration commands.

    python -m app.cli create-admin --email admin@example.org --full-name "Jane Admin"
    python -m app.cli reset-password --email admin@example.org

Passwords are prompted twice (or read from ``APP_BOOTSTRAP_ADMIN_PASSWORD`` /
``APP_NEW_PASSWORD`` for automation), never passed as arguments, so they do not end up in the
shell history or the process list.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from app import models  # noqa: F401
from app.core.config import Settings, get_settings
from app.core.errors import DomainError
from app.core.security import hash_password
from app.db.session import create_db_engine, create_session_factory
from app.models import Role, User
from app.repositories import UnitOfWork
from app.services.auth import validate_password_strength


def _error(message: str) -> int:
    print(f"erreur : {message}", file=sys.stderr)
    return 1


def _read_password(env_var: str, settings: Settings, email: str) -> str | None:
    """Password from the environment (automation) or typed twice; ``None`` if invalid."""
    password = os.environ.get(env_var)
    if not password:
        password = getpass.getpass("Mot de passe : ")
        if getpass.getpass("Confirmez le mot de passe : ") != password:
            _error("les deux mots de passe ne correspondent pas")
            return None
    try:
        validate_password_strength(password, settings, email=email)
    except DomainError as exc:
        _error(exc.message)
        return None
    return password


@contextmanager
def _unit_of_work(settings: Settings) -> Iterator[UnitOfWork]:
    engine = create_db_engine(settings.database_url)
    try:
        with create_session_factory(engine)() as session:
            yield UnitOfWork(session)
    finally:
        engine.dispose()


def create_admin(email: str, full_name: str) -> int:
    settings = get_settings()
    with _unit_of_work(settings) as uow:
        if uow.users.get_by_email(email):
            return _error(
                "un utilisateur existe déjà avec cet e-mail "
                "(pour changer son mot de passe : python -m app.cli reset-password --email ...)"
            )
        password = _read_password("APP_BOOTSTRAP_ADMIN_PASSWORD", settings, email)
        if password is None:
            return 1
        uow.users.add(
            User(
                email=email.lower(),
                full_name=full_name,
                role=Role.ADMIN,
                hashed_password=hash_password(password),
                is_active=True,
                token_version=0,
            )
        )
        uow.commit()
    print("Administrateur créé.")
    return 0


def reset_password(email: str) -> int:
    """Set a new password for an existing account and close all of its sessions."""
    settings = get_settings()
    with _unit_of_work(settings) as uow:
        user = uow.users.get_by_email(email)
        if user is None:
            return _error("aucun utilisateur avec cet e-mail")
        if user.anonymized_at is not None:
            return _error("ce compte a été anonymisé (RGPD) et ne peut plus être utilisé")
        password = _read_password("APP_NEW_PASSWORD", settings, user.email)
        if password is None:
            return 1
        user.hashed_password = hash_password(password)
        # Same effect as a password change: every existing token stops working.
        user.token_version += 1
        uow.refresh_tokens.revoke_all_for_user(user.id, datetime.now(UTC))
        uow.commit()
        active = user.is_active
    print("Mot de passe modifié. Toutes les sessions de ce compte ont été fermées.")
    if not active:
        print(
            "Attention : ce compte est désactivé. Un administrateur doit le réactiver "
            "(page Utilisateurs) avant qu'il puisse se connecter."
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-admin", help="Créer un compte administrateur")
    admin.add_argument("--email", required=True)
    admin.add_argument("--full-name", required=True)
    reset = sub.add_parser("reset-password", help="Définir un nouveau mot de passe")
    reset.add_argument("--email", required=True)
    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return create_admin(args.email, args.full_name)
    if args.command == "reset-password":
        return reset_password(args.email)
    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
