from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, PaginationDep, Policy, UserServiceDep, require
from app.domain.rbac import Permission
from app.models import Role
from app.schemas.common import Page
from app.schemas.users import PersonalDataExport, UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["Utilisateurs & RGPD"])


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.get("/me/export", response_model=PersonalDataExport)
def export_my_data(user: CurrentUser, users: UserServiceDep) -> PersonalDataExport:
    """RGPD art. 15 & 20 - download every personal data held about the current user."""
    return users.export_personal_data(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def erase_my_account(policy: Policy, users: UserServiceDep) -> None:
    """RGPD art. 17 - anonymize the current account (maintenance records are retained)."""
    users.anonymize(policy, policy.user.id)


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require(Permission.USER_MANAGE))],
)
def create_user(body: UserCreate, policy: Policy, users: UserServiceDep) -> UserRead:
    return UserRead.model_validate(users.create(policy, body))


@router.get(
    "", response_model=Page[UserRead], dependencies=[Depends(require(Permission.USER_MANAGE))]
)
def list_users(
    policy: Policy,
    users: UserServiceDep,
    page: PaginationDep,
    role: Role | None = None,
    site_id: uuid.UUID | None = Query(default=None),
) -> Page[UserRead]:
    items, total = users.search(
        policy, offset=page.offset, limit=page.limit, role=role, site_id=site_id
    )
    return Page(
        items=[UserRead.model_validate(u) for u in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/{user_id}", response_model=UserRead, dependencies=[Depends(require(Permission.USER_MANAGE))]
)
def get_user(user_id: uuid.UUID, policy: Policy, users: UserServiceDep) -> UserRead:
    return UserRead.model_validate(users.get(policy, user_id))


@router.patch(
    "/{user_id}", response_model=UserRead, dependencies=[Depends(require(Permission.USER_MANAGE))]
)
def update_user(
    user_id: uuid.UUID, body: UserUpdate, policy: Policy, users: UserServiceDep
) -> UserRead:
    return UserRead.model_validate(users.update(policy, user_id, body))


@router.post("/{user_id}/anonymize", response_model=UserRead)
def anonymize_user(user_id: uuid.UUID, policy: Policy, users: UserServiceDep) -> UserRead:
    """RGPD art. 17 - erasure request handled by an administrator."""
    return UserRead.model_validate(users.anonymize(policy, user_id))
