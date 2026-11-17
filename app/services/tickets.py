from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.domain.rbac import AccessPolicy, Permission
from app.domain.workflow import is_reopening, validate_transition
from app.models import (
    Role,
    Ticket,
    TicketEvent,
    TicketEventType,
    TicketStatus,
    User,
)
from app.notifications import NotificationScheduler
from app.notifications.messages import assignment_notification, status_change_notification
from app.repositories import TicketFilter, UnitOfWork
from app.schemas.tickets import (
    TicketAssignment,
    TicketCreate,
    TicketLocation,
    TicketStatusChange,
    TicketUpdate,
)


class TicketService:
    def __init__(self, uow: UnitOfWork, notifications: NotificationScheduler) -> None:
        self.uow = uow
        self.notifications = notifications

    # -- queries --------------------------------------------------------------------------
    def get(self, policy: AccessPolicy, ticket_id: uuid.UUID) -> Ticket:
        policy.require(Permission.TICKET_READ)
        return policy.require_ticket(self.uow.tickets.get(ticket_id))

    def search(
        self, policy: AccessPolicy, filters: TicketFilter, *, offset: int, limit: int
    ) -> tuple[list[Ticket], int]:
        policy.require(Permission.TICKET_READ)
        if filters.include_archived:
            policy.require(Permission.HISTORY_READ)
        scoped = TicketFilter(
            restrict_to_sites=policy.accessible_site_ids(),
            site_id=filters.site_id,
            status=filters.status,
            priority=filters.priority,
            assignee_user_id=filters.assignee_user_id,
            assignee_provider_id=filters.assignee_provider_id,
            include_archived=filters.include_archived,
        )
        return self.uow.tickets.search(scoped, offset=offset, limit=limit)

    def history(self, policy: AccessPolicy, ticket_id: uuid.UUID) -> list[TicketEvent]:
        policy.require(Permission.HISTORY_READ)
        ticket = self.get(policy, ticket_id)
        return self.uow.ticket_events.list_for_ticket(ticket.id)

    def site_history(
        self, policy: AccessPolicy, site_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[TicketEvent], int]:
        policy.require(Permission.HISTORY_READ)
        policy.require_site(site_id)
        return self.uow.ticket_events.list_for_site(site_id, offset=offset, limit=limit)

    # -- commands -------------------------------------------------------------------------
    def create(self, policy: AccessPolicy, data: TicketCreate) -> Ticket:
        policy.require(Permission.TICKET_CREATE)
        policy.require_site(data.site_id)
        site = self.uow.sites.get(data.site_id)
        if site is None:
            raise NotFoundError("Site not found")
        if not site.is_active:
            raise BusinessRuleError("Cannot open a ticket on an inactive site")
        ticket = Ticket(
            site_id=site.id,
            title=data.title,
            description=data.description,
            priority=data.priority,
            status=TicketStatus.TODO,
            created_by_id=policy.user.id,
            **self._location_columns(data.location),
        )
        self.uow.tickets.add(ticket)
        self._record(ticket, policy.user, TicketEventType.CREATED, to_status=TicketStatus.TODO)
        self._commit()
        return ticket

    def update(self, policy: AccessPolicy, ticket_id: uuid.UUID, data: TicketUpdate) -> Ticket:
        policy.require(Permission.TICKET_UPDATE)
        ticket = self._get_mutable(policy, ticket_id)
        changes = data.model_dump(exclude_unset=True, exclude={"location"})
        if data.location is not None:
            changes |= self._location_columns(data.location)
        changed = {k: v for k, v in changes.items() if getattr(ticket, k) != v}
        if not changed:
            return ticket
        for field, value in changed.items():
            setattr(ticket, field, value)
        self._record(
            ticket, policy.user, TicketEventType.UPDATED, details={"fields": sorted(changed)}
        )
        self._commit()
        return ticket

    def assign(self, policy: AccessPolicy, ticket_id: uuid.UUID, data: TicketAssignment) -> Ticket:
        policy.require(Permission.TICKET_ASSIGN)
        ticket = self._get_mutable(policy, ticket_id)
        if ticket.status is TicketStatus.DONE:
            raise BusinessRuleError("Completed tickets cannot be reassigned")

        details: dict[str, Any]
        if data.technician_id is not None:
            technician = self.uow.users.get(data.technician_id)
            if technician is None or technician.role is not Role.TECHNICIAN:
                raise NotFoundError("Technician not found")
            if not technician.is_active:
                raise BusinessRuleError("Technician account is inactive")
            if ticket.site_id not in technician.site_ids:
                raise BusinessRuleError("Technician is not attached to this ticket's site")
            ticket.assignee_user, ticket.assignee_provider = technician, None
            ticket.assignee_user_id, ticket.assignee_provider_id = technician.id, None
            details = {"assignee_type": "technician", "assignee_id": str(technician.id)}
        elif data.provider_id is not None:
            provider = self.uow.providers.get(data.provider_id)
            if provider is None:
                raise NotFoundError("Provider not found")
            if not provider.is_active:
                raise BusinessRuleError("Provider is inactive")
            ticket.assignee_user, ticket.assignee_provider = None, provider
            ticket.assignee_user_id, ticket.assignee_provider_id = None, provider.id
            details = {"assignee_type": "provider", "assignee_id": str(provider.id)}
        else:
            if ticket.status is TicketStatus.IN_PROGRESS:
                raise BusinessRuleError("An in-progress ticket cannot be left unassigned")
            ticket.assignee_user = ticket.assignee_provider = None
            ticket.assignee_user_id = ticket.assignee_provider_id = None
            self._record(ticket, policy.user, TicketEventType.UNASSIGNED)
            self._commit()
            return ticket

        self._record(ticket, policy.user, TicketEventType.ASSIGNED, details=details)
        self._commit()
        self.notifications.schedule(assignment_notification(ticket))
        return ticket

    def change_status(
        self, policy: AccessPolicy, ticket_id: uuid.UUID, data: TicketStatusChange
    ) -> Ticket:
        ticket = self.get(policy, ticket_id)
        policy.require_status_change(ticket)
        validate_transition(ticket, data.status, data.comment)
        if is_reopening(ticket, data.status):
            policy.require(Permission.TICKET_REOPEN)

        previous = ticket.status
        now = datetime.now(UTC)
        ticket.status = data.status
        if data.status is TicketStatus.IN_PROGRESS and ticket.started_at is None:
            ticket.started_at = now
        ticket.closed_at = now if data.status is TicketStatus.DONE else None
        self._record(
            ticket,
            policy.user,
            TicketEventType.STATUS_CHANGED,
            from_status=previous,
            to_status=data.status,
            comment=data.comment,
        )
        self._commit()
        self.notifications.schedule(status_change_notification(ticket, previous, data.comment))
        return ticket

    def archive(self, policy: AccessPolicy, ticket_id: uuid.UUID) -> Ticket:
        policy.require(Permission.TICKET_ARCHIVE)
        ticket = self._get_mutable(policy, ticket_id)
        if ticket.status is not TicketStatus.DONE:
            raise BusinessRuleError("Only completed tickets can be archived")
        ticket.archived_at = datetime.now(UTC)
        self._record(ticket, policy.user, TicketEventType.ARCHIVED)
        self._commit()
        return ticket

    # -- helpers --------------------------------------------------------------------------
    def _get_mutable(self, policy: AccessPolicy, ticket_id: uuid.UUID) -> Ticket:
        ticket = self.get(policy, ticket_id)
        if ticket.is_archived:
            raise BusinessRuleError("Archived tickets are read-only")
        return ticket

    @staticmethod
    def _location_columns(location: TicketLocation) -> dict[str, Any]:
        return {
            "location_building": location.building,
            "location_floor": location.floor,
            "location_room": location.room,
            "location_details": location.details,
        }

    def _record(
        self,
        ticket: Ticket,
        actor: User,
        event_type: TicketEventType,
        *,
        from_status: TicketStatus | None = None,
        to_status: TicketStatus | None = None,
        comment: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.uow.ticket_events.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_id=actor.id,
                event_type=event_type,
                from_status=from_status,
                to_status=to_status,
                comment=comment,
                details=details or {},
            )
        )

    def record_event(
        self, ticket: Ticket, actor: User, event_type: TicketEventType, details: dict[str, Any]
    ) -> None:
        """Hook for other modules (photos, future signatures...) to write to the audit trail."""
        self._record(ticket, actor, event_type, details=details)

    def _commit(self) -> None:
        try:
            self.uow.commit()
        except StaleDataError as exc:
            self.uow.rollback()
            raise ConflictError("The ticket was modified concurrently, please retry") from exc
