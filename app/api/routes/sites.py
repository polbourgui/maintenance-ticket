from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    PaginationDep,
    Policy,
    ProviderServiceDep,
    SiteServiceDep,
    TicketServiceDep,
    require,
)
from app.domain.rbac import Permission
from app.schemas.common import Page
from app.schemas.providers import ProviderCreate, ProviderRead, ProviderUpdate
from app.schemas.sites import MembershipRequest, SiteCreate, SiteRead, SiteUpdate
from app.schemas.tickets import TicketEventRead

router = APIRouter(prefix="/sites", tags=["Établissements"])
providers_router = APIRouter(prefix="/providers", tags=["Prestataires"])


@router.post(
    "",
    response_model=SiteRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require(Permission.SITE_MANAGE))],
)
def create_site(body: SiteCreate, policy: Policy, sites: SiteServiceDep) -> SiteRead:
    return SiteRead.model_validate(sites.create(policy, body))


@router.get("", response_model=Page[SiteRead])
def list_sites(policy: Policy, sites: SiteServiceDep, page: PaginationDep) -> Page[SiteRead]:
    items, total = sites.search(policy, offset=page.offset, limit=page.limit)
    return Page(
        items=[SiteRead.model_validate(s) for s in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{site_id}", response_model=SiteRead)
def get_site(site_id: uuid.UUID, policy: Policy, sites: SiteServiceDep) -> SiteRead:
    return SiteRead.model_validate(sites.get(policy, site_id))


@router.patch(
    "/{site_id}", response_model=SiteRead, dependencies=[Depends(require(Permission.SITE_MANAGE))]
)
def update_site(
    site_id: uuid.UUID, body: SiteUpdate, policy: Policy, sites: SiteServiceDep
) -> SiteRead:
    return SiteRead.model_validate(sites.update(policy, site_id, body))


@router.post(
    "/{site_id}/members",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require(Permission.SITE_MANAGE))],
)
def add_member(
    site_id: uuid.UUID, body: MembershipRequest, policy: Policy, sites: SiteServiceDep
) -> None:
    sites.add_member(policy, site_id, body.user_id)


@router.delete(
    "/{site_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require(Permission.SITE_MANAGE))],
)
def remove_member(
    site_id: uuid.UUID, user_id: uuid.UUID, policy: Policy, sites: SiteServiceDep
) -> None:
    sites.remove_member(policy, site_id, user_id)


@router.get("/{site_id}/history", response_model=Page[TicketEventRead])
def site_history(
    site_id: uuid.UUID, policy: Policy, tickets: TicketServiceDep, page: PaginationDep
) -> Page[TicketEventRead]:
    """Complete, immutable intervention history of a site (archived tickets included)."""
    items, total = tickets.site_history(policy, site_id, offset=page.offset, limit=page.limit)
    return Page(
        items=[TicketEventRead.model_validate(e) for e in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@providers_router.post(
    "",
    response_model=ProviderRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require(Permission.PROVIDER_MANAGE))],
)
def create_provider(
    body: ProviderCreate, policy: Policy, providers: ProviderServiceDep
) -> ProviderRead:
    return ProviderRead.model_validate(providers.create(policy, body))


@providers_router.get("", response_model=Page[ProviderRead])
def list_providers(
    policy: Policy, providers: ProviderServiceDep, page: PaginationDep, active_only: bool = True
) -> Page[ProviderRead]:
    items, total = providers.search(
        policy, offset=page.offset, limit=page.limit, active_only=active_only
    )
    return Page(
        items=[ProviderRead.model_validate(p) for p in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@providers_router.patch(
    "/{provider_id}",
    response_model=ProviderRead,
    dependencies=[Depends(require(Permission.PROVIDER_MANAGE))],
)
def update_provider(
    provider_id: uuid.UUID, body: ProviderUpdate, policy: Policy, providers: ProviderServiceDep
) -> ProviderRead:
    return ProviderRead.model_validate(providers.update(policy, provider_id, body))
