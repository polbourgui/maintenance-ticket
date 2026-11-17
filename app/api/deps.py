"""FastAPI dependency wiring (composition root for request-scoped objects)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import BackgroundTasks, Depends, Query, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.rate_limit import RateLimiter
from app.domain.rbac import AccessPolicy, Permission
from app.models import User
from app.notifications import BackgroundNotificationScheduler, NotificationDispatcher
from app.repositories import UnitOfWork
from app.services.auth import AuthService
from app.services.photos import PhotoService
from app.services.reports import ReportService
from app.services.sites import ProviderService, SiteService
from app.services.tickets import TicketService
from app.services.users import UserService
from app.storage import FileStorage

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_session(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_uow(session: Annotated[Session, Depends(get_session)]) -> UnitOfWork:
    return UnitOfWork(session)


def get_dispatcher(request: Request) -> NotificationDispatcher:
    dispatcher: NotificationDispatcher = request.app.state.dispatcher
    return dispatcher


def get_storage(request: Request) -> FileStorage:
    storage: FileStorage = request.app.state.storage
    return storage


def get_rate_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.login_rate_limiter
    return limiter


UoWDep = Annotated[UnitOfWork, Depends(get_uow)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_auth_service(
    uow: UoWDep, settings: SettingsDep, limiter: Annotated[RateLimiter, Depends(get_rate_limiter)]
) -> AuthService:
    return AuthService(uow, settings, limiter)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], auth: AuthServiceDep) -> User:
    return auth.authenticate(token)


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_policy(user: CurrentUser) -> AccessPolicy:
    return AccessPolicy(user)


Policy = Annotated[AccessPolicy, Depends(get_policy)]


def require(permission: Permission) -> Callable[[AccessPolicy], AccessPolicy]:
    """Route-level guard; services re-check permissions (defence in depth)."""

    def _guard(policy: Policy) -> AccessPolicy:
        policy.require(permission)
        return policy

    return _guard


def get_ticket_service(
    uow: UoWDep,
    background_tasks: BackgroundTasks,
    dispatcher: Annotated[NotificationDispatcher, Depends(get_dispatcher)],
) -> TicketService:
    return TicketService(uow, BackgroundNotificationScheduler(background_tasks, dispatcher))


TicketServiceDep = Annotated[TicketService, Depends(get_ticket_service)]


def get_photo_service(
    tickets: TicketServiceDep, storage: Annotated[FileStorage, Depends(get_storage)]
) -> PhotoService:
    return PhotoService(tickets, storage)


def get_user_service(uow: UoWDep, settings: SettingsDep) -> UserService:
    return UserService(uow, settings)


def get_site_service(uow: UoWDep) -> SiteService:
    return SiteService(uow)


def get_provider_service(uow: UoWDep) -> ProviderService:
    return ProviderService(uow)


def get_report_service(uow: UoWDep) -> ReportService:
    return ReportService(uow)


PhotoServiceDep = Annotated[PhotoService, Depends(get_photo_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
SiteServiceDep = Annotated[SiteService, Depends(get_site_service)]
ProviderServiceDep = Annotated[ProviderService, Depends(get_provider_service)]
ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]


class Pagination:
    def __init__(
        self,
        offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> None:
        self.offset = offset
        self.limit = limit


PaginationDep = Annotated[Pagination, Depends()]
