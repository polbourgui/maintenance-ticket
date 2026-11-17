"""Role-Based Access Control.

Two layers are enforced on every request:

1. **Role permissions** - what an action type a role may perform at all (``ROLE_PERMISSIONS``).
2. **Site scoping** - non-admin users only ever see resources of the sites they are members of.
   Out-of-scope resources answer *404* (not 403) so that their existence is not leaked.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from app.core.errors import NotFoundError, PermissionDeniedError
from app.models import Role, Ticket, User


class Permission(StrEnum):
    TICKET_CREATE = "ticket:create"
    TICKET_READ = "ticket:read"
    TICKET_UPDATE = "ticket:update"
    TICKET_ASSIGN = "ticket:assign"
    TICKET_CHANGE_STATUS = "ticket:change_status"
    TICKET_REOPEN = "ticket:reopen"
    TICKET_ARCHIVE = "ticket:archive"
    PHOTO_UPLOAD = "photo:upload"
    PHOTO_READ = "photo:read"
    SITE_READ = "site:read"
    SITE_MANAGE = "site:manage"
    USER_MANAGE = "user:manage"
    PROVIDER_READ = "provider:read"
    PROVIDER_MANAGE = "provider:manage"
    REPORT_READ = "report:read"
    HISTORY_READ = "history:read"
    NOTIFICATION_TEST = "notification:test"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.TECHNICIAN: frozenset(
        {
            Permission.TICKET_CREATE,
            Permission.TICKET_READ,
            Permission.TICKET_UPDATE,
            Permission.TICKET_CHANGE_STATUS,
            Permission.PHOTO_UPLOAD,
            Permission.PHOTO_READ,
            Permission.SITE_READ,
            Permission.PROVIDER_READ,
            Permission.REPORT_READ,
            Permission.HISTORY_READ,
        }
    ),
    Role.CLIENT: frozenset(
        {
            Permission.TICKET_CREATE,
            Permission.TICKET_READ,
            Permission.PHOTO_READ,
            Permission.SITE_READ,
            Permission.REPORT_READ,
            Permission.HISTORY_READ,
        }
    ),
}


class AccessPolicy:
    """Authorization decisions for one authenticated user."""

    def __init__(self, user: User) -> None:
        self.user = user
        self._permissions = ROLE_PERMISSIONS[user.role]

    @property
    def is_admin(self) -> bool:
        return self.user.role is Role.ADMIN

    def has(self, permission: Permission) -> bool:
        return permission in self._permissions

    def require(self, permission: Permission) -> None:
        if not self.has(permission):
            raise PermissionDeniedError("You are not allowed to perform this action")

    def accessible_site_ids(self) -> set[uuid.UUID] | None:
        """``None`` means *every* site (admin)."""
        return None if self.is_admin else self.user.site_ids

    def can_access_site(self, site_id: uuid.UUID) -> bool:
        return self.is_admin or site_id in self.user.site_ids

    def require_site(self, site_id: uuid.UUID) -> None:
        if not self.can_access_site(site_id):
            raise NotFoundError("Site not found")

    def require_ticket(self, ticket: Ticket | None) -> Ticket:
        if ticket is None or not self.can_access_site(ticket.site_id):
            raise NotFoundError("Ticket not found")
        return ticket

    def require_status_change(self, ticket: Ticket) -> None:
        """Admins may change any status; technicians only on tickets assigned to them."""
        self.require(Permission.TICKET_CHANGE_STATUS)
        if self.is_admin:
            return
        if ticket.assignee_user_id != self.user.id:
            raise PermissionDeniedError(
                "Only the assigned technician can change this ticket status"
            )
