"""Administration commands.

    python -m app.cli create-admin --email admin@example.org --full-name "Jane Admin"

The password is read from ``APP_BOOTSTRAP_ADMIN_PASSWORD`` or prompted (never passed as an
argument, so it does not end up in the shell history / process list).
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from app import models  # noqa: F401
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.security import hash_password
from app.db.session import create_db_engine, create_session_factory
from app.models import Role, User
from app.repositories import UnitOfWork
from app.services.auth import validate_password_strength


def create_admin(email: str, full_name: str) -> int:
    settings = get_settings()
    password = os.environ.get("APP_BOOTSTRAP_ADMIN_PASSWORD") or getpass.getpass("Password: ")
    try:
        validate_password_strength(password, settings, email=email)
    except DomainError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 1
    session = create_session_factory(create_db_engine(settings.database_url))()
    with session:
        uow = UnitOfWork(session)
        if uow.users.get_by_email(email):
            print("error: user already exists", file=sys.stderr)
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
    print("admin created")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-admin", help="Create an administrator account")
    admin.add_argument("--email", required=True)
    admin.add_argument("--full-name", required=True)
    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return create_admin(args.email, args.full_name)
    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
