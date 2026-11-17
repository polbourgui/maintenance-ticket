from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def create_db_engine(database_url: str, *, echo: bool = False) -> Engine:
    kwargs: dict[str, Any] = {"echo": echo, "pool_pre_ping": True}
    is_sqlite = database_url.startswith("sqlite")
    if is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}
        if database_url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, **kwargs)

    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _enable_sqlite_fk(dbapi_connection: Any, _record: Any) -> None:  # noqa: ANN401
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
