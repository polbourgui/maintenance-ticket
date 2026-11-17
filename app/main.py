"""Application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (registers tables)
from app.api.errors import register_error_handlers
from app.api.routes import auth, reports, sites, system, tickets, users
from app.api.spa import mount_spa
from app.core.config import Settings, get_settings
from app.core.middleware import SecurityHeadersMiddleware
from app.core.rate_limit import InMemoryRateLimiter
from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory
from app.notifications import build_dispatcher
from app.storage import LocalFileStorage

DESCRIPTION = """
API de gestion des **tickets de maintenance** pour un groupe d'établissements recevant du
public (ERP).

* Authentification : OAuth2 *password flow* → JWT d'accès court + refresh token rotatif.
* RBAC : `admin`, `technician`, `client`, cloisonnement par établissement.
* Notifications e-mail sur assignation et changement de statut.
"""


def _configure_logging() -> None:
    logger = logging.getLogger("app")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    _configure_logging()
    engine = create_db_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if settings.auto_create_tables:
            Base.metadata.create_all(engine)
        yield
        engine.dispose()

    docs = settings.docs_enabled
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.dispatcher = build_dispatcher(settings)
    app.state.storage = LocalFileStorage(settings.upload_dir)
    app.state.login_rate_limiter = InMemoryRateLimiter(
        settings.login_max_attempts, settings.login_window_seconds
    )

    app.add_middleware(
        SecurityHeadersMiddleware, hsts=settings.is_production, api_prefix=settings.api_prefix
    )
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )
    register_error_handlers(app)

    api = APIRouter(prefix=settings.api_prefix)
    for router in (
        auth.router,
        users.router,
        sites.router,
        sites.providers_router,
        tickets.router,
        reports.router,
        system.router,
    ):
        api.include_router(router)
    app.include_router(api)
    if settings.frontend_dist is not None:
        mount_spa(app, settings.frontend_dist, api_prefix=settings.api_prefix)
    return app
