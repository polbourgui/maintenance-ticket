from __future__ import annotations

import uuid

from app.core.errors import ConflictError, NotFoundError
from app.domain.rbac import AccessPolicy, Permission
from app.models import Provider, Site
from app.repositories import UnitOfWork
from app.schemas.providers import ProviderCreate, ProviderUpdate
from app.schemas.sites import SiteCreate, SiteUpdate


class SiteService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def create(self, policy: AccessPolicy, data: SiteCreate) -> Site:
        policy.require(Permission.SITE_MANAGE)
        if self.uow.sites.get_by_code(data.code) is not None:
            raise ConflictError("A site with this code already exists")
        site = self.uow.sites.add(Site(**data.model_dump(), is_active=True))
        self.uow.commit()
        return site

    def search(self, policy: AccessPolicy, *, offset: int, limit: int) -> tuple[list[Site], int]:
        policy.require(Permission.SITE_READ)
        return self.uow.sites.search(
            offset=offset, limit=limit, restrict_to=policy.accessible_site_ids()
        )

    def get(self, policy: AccessPolicy, site_id: uuid.UUID) -> Site:
        policy.require(Permission.SITE_READ)
        policy.require_site(site_id)
        site = self.uow.sites.get(site_id)
        if site is None:
            raise NotFoundError("Site not found")
        return site

    def update(self, policy: AccessPolicy, site_id: uuid.UUID, data: SiteUpdate) -> Site:
        policy.require(Permission.SITE_MANAGE)
        site = self.get(policy, site_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(site, field, value)
        self.uow.commit()
        return site

    def add_member(self, policy: AccessPolicy, site_id: uuid.UUID, user_id: uuid.UUID) -> None:
        policy.require(Permission.SITE_MANAGE)
        site = self.get(policy, site_id)
        user = self.uow.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        if site not in user.sites:
            user.sites.append(site)
        self.uow.commit()

    def remove_member(self, policy: AccessPolicy, site_id: uuid.UUID, user_id: uuid.UUID) -> None:
        policy.require(Permission.SITE_MANAGE)
        site = self.get(policy, site_id)
        user = self.uow.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        if site in user.sites:
            user.sites.remove(site)
        self.uow.commit()


class ProviderService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def create(self, policy: AccessPolicy, data: ProviderCreate) -> Provider:
        policy.require(Permission.PROVIDER_MANAGE)
        provider = self.uow.providers.add(
            Provider(**data.model_dump() | {"email": data.email.lower()}, is_active=True)
        )
        self.uow.commit()
        return provider

    def search(
        self, policy: AccessPolicy, *, offset: int, limit: int, active_only: bool
    ) -> tuple[list[Provider], int]:
        policy.require(Permission.PROVIDER_READ)
        return self.uow.providers.search(offset=offset, limit=limit, active_only=active_only)

    def update(
        self, policy: AccessPolicy, provider_id: uuid.UUID, data: ProviderUpdate
    ) -> Provider:
        policy.require(Permission.PROVIDER_MANAGE)
        provider = self.uow.providers.get(provider_id)
        if provider is None:
            raise NotFoundError("Provider not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(provider, field, value)
        self.uow.commit()
        return provider
