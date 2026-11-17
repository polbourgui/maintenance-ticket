from __future__ import annotations

import uuid

import pytest

from app.core.errors import NotFoundError, PermissionDeniedError
from app.domain.rbac import ROLE_PERMISSIONS, AccessPolicy, Permission
from app.models import Role, Site, Ticket, TicketPriority, TicketStatus, User


def _user(role: Role, sites: list[Site] | None = None) -> User:
    user = User(
        id=uuid.uuid4(), email="u@example.org", full_name="U", role=role, hashed_password="x"
    )
    user.sites = sites or []
    return user


def _site() -> Site:
    return Site(
        id=uuid.uuid4(),
        code="S",
        name="S",
        address="a",
        postal_code="1",
        city="c",
        erp_type="M",
        erp_category=1,
    )


def _ticket(site: Site, assignee: uuid.UUID | None = None) -> Ticket:
    return Ticket(
        id=uuid.uuid4(),
        site_id=site.id,
        title="t",
        description="d",
        priority=TicketPriority.LOW,
        status=TicketStatus.TODO,
        location_room="r",
        created_by_id=uuid.uuid4(),
        assignee_user_id=assignee,
    )


# Expected permission matrix, written independently from the implementation.
EXPECTED = {
    Permission.TICKET_CREATE: {Role.ADMIN, Role.TECHNICIAN, Role.CLIENT},
    Permission.TICKET_READ: {Role.ADMIN, Role.TECHNICIAN, Role.CLIENT},
    Permission.TICKET_UPDATE: {Role.ADMIN, Role.TECHNICIAN},
    Permission.TICKET_ASSIGN: {Role.ADMIN},
    Permission.TICKET_CHANGE_STATUS: {Role.ADMIN, Role.TECHNICIAN},
    Permission.TICKET_REOPEN: {Role.ADMIN},
    Permission.TICKET_ARCHIVE: {Role.ADMIN},
    Permission.PHOTO_UPLOAD: {Role.ADMIN, Role.TECHNICIAN},
    Permission.PHOTO_READ: {Role.ADMIN, Role.TECHNICIAN, Role.CLIENT},
    Permission.SITE_READ: {Role.ADMIN, Role.TECHNICIAN, Role.CLIENT},
    Permission.SITE_MANAGE: {Role.ADMIN},
    Permission.USER_MANAGE: {Role.ADMIN},
    Permission.PROVIDER_READ: {Role.ADMIN, Role.TECHNICIAN},
    Permission.PROVIDER_MANAGE: {Role.ADMIN},
    Permission.REPORT_READ: {Role.ADMIN, Role.TECHNICIAN, Role.CLIENT},
    Permission.HISTORY_READ: {Role.ADMIN, Role.TECHNICIAN, Role.CLIENT},
    Permission.NOTIFICATION_TEST: {Role.ADMIN},
}


def test_matrix_covers_every_permission() -> None:
    assert set(EXPECTED) == set(Permission)


@pytest.mark.parametrize("permission", list(Permission))
@pytest.mark.parametrize("role", list(Role))
def test_permission_matrix(role: Role, permission: Permission) -> None:
    assert (permission in ROLE_PERMISSIONS[role]) is (role in EXPECTED[permission])
    policy = AccessPolicy(_user(role))
    if role in EXPECTED[permission]:
        policy.require(permission)
    else:
        with pytest.raises(PermissionDeniedError):
            policy.require(permission)


def test_site_scoping() -> None:
    a, b = _site(), _site()
    tech = AccessPolicy(_user(Role.TECHNICIAN, [a]))
    admin = AccessPolicy(_user(Role.ADMIN))
    assert tech.accessible_site_ids() == {a.id}
    assert admin.accessible_site_ids() is None
    assert tech.require_ticket(_ticket(a))
    with pytest.raises(NotFoundError):
        tech.require_ticket(_ticket(b))
    with pytest.raises(NotFoundError):
        tech.require_ticket(None)
    admin.require_site(b.id)


def test_status_change_requires_assignment_for_technicians() -> None:
    site = _site()
    user = _user(Role.TECHNICIAN, [site])
    policy = AccessPolicy(user)
    policy.require_status_change(_ticket(site, assignee=user.id))
    with pytest.raises(PermissionDeniedError):
        policy.require_status_change(_ticket(site, assignee=uuid.uuid4()))
    with pytest.raises(PermissionDeniedError):
        AccessPolicy(_user(Role.CLIENT, [site])).require_status_change(_ticket(site))
    AccessPolicy(_user(Role.ADMIN)).require_status_change(_ticket(site))
