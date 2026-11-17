from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select

from app.models import Ticket, TicketEvent, TicketPhoto, TicketPriority, TicketStatus
from app.repositories.base import SQLAlchemyRepository


@dataclass(frozen=True, slots=True)
class TicketFilter:
    restrict_to_sites: set[uuid.UUID] | None = None  # None = no restriction (admin)
    site_id: uuid.UUID | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignee_user_id: uuid.UUID | None = None
    assignee_provider_id: uuid.UUID | None = None
    include_archived: bool = False


@dataclass(frozen=True, slots=True)
class SiteTicketStats:
    site_id: uuid.UUID
    by_status: dict[TicketStatus, int]
    by_priority: dict[TicketPriority, int]
    archived: int
    avg_resolution_hours: float | None


class TicketRepository(SQLAlchemyRepository[Ticket]):
    model = Ticket

    def search(self, filters: TicketFilter, *, offset: int, limit: int) -> tuple[list[Ticket], int]:
        stmt = select(Ticket).order_by(Ticket.created_at.desc(), Ticket.id)
        if filters.restrict_to_sites is not None:
            stmt = stmt.where(Ticket.site_id.in_(filters.restrict_to_sites))
        if filters.site_id is not None:
            stmt = stmt.where(Ticket.site_id == filters.site_id)
        if filters.status is not None:
            stmt = stmt.where(Ticket.status == filters.status)
        if filters.priority is not None:
            stmt = stmt.where(Ticket.priority == filters.priority)
        if filters.assignee_user_id is not None:
            stmt = stmt.where(Ticket.assignee_user_id == filters.assignee_user_id)
        if filters.assignee_provider_id is not None:
            stmt = stmt.where(Ticket.assignee_provider_id == filters.assignee_provider_id)
        if not filters.include_archived:
            stmt = stmt.where(Ticket.archived_at.is_(None))
        return self._paginate(stmt, offset=offset, limit=limit)

    def list_created_by(self, user_id: uuid.UUID) -> list[Ticket]:
        stmt = select(Ticket).where(Ticket.created_by_id == user_id).order_by(Ticket.created_at)
        return list(self.session.scalars(stmt).unique())

    def stats_for_site(self, site_id: uuid.UUID) -> SiteTicketStats:
        status_rows = self.session.execute(
            select(Ticket.status, func.count())
            .where(Ticket.site_id == site_id)
            .group_by(Ticket.status)
        ).all()
        priority_rows = self.session.execute(
            select(Ticket.priority, func.count())
            .where(Ticket.site_id == site_id, Ticket.status != TicketStatus.DONE)
            .group_by(Ticket.priority)
        ).all()
        archived = self.session.scalar(
            select(func.count()).where(Ticket.site_id == site_id, Ticket.archived_at.is_not(None))
        )
        # Resolution time is computed in Python to stay portable across SQLite / PostgreSQL.
        rows = self.session.execute(
            select(Ticket.created_at, Ticket.closed_at).where(
                Ticket.site_id == site_id, Ticket.closed_at.is_not(None)
            )
        ).all()
        resolved: list[tuple[datetime, datetime]] = [
            (created, closed) for created, closed in rows if closed is not None
        ]
        avg_hours = (
            sum((closed - created).total_seconds() for created, closed in resolved)
            / len(resolved)
            / 3600
            if resolved
            else None
        )
        by_status = dict.fromkeys(TicketStatus, 0)
        by_status.update({TicketStatus(s): n for s, n in status_rows})
        by_priority = dict.fromkeys(TicketPriority, 0)
        by_priority.update({TicketPriority(p): n for p, n in priority_rows})
        return SiteTicketStats(
            site_id=site_id,
            by_status=by_status,
            by_priority=by_priority,
            archived=archived or 0,
            avg_resolution_hours=round(avg_hours, 2) if avg_hours is not None else None,
        )


class TicketEventRepository(SQLAlchemyRepository[TicketEvent]):
    model = TicketEvent

    def list_for_ticket(self, ticket_id: uuid.UUID) -> list[TicketEvent]:
        stmt = (
            select(TicketEvent)
            .where(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.created_at, TicketEvent.id)
        )
        return list(self.session.scalars(stmt))

    def list_for_site(
        self, site_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[TicketEvent], int]:
        stmt = (
            select(TicketEvent)
            .join(Ticket, Ticket.id == TicketEvent.ticket_id)
            .where(Ticket.site_id == site_id)
            .order_by(TicketEvent.created_at.desc(), TicketEvent.id)
        )
        return self._paginate(stmt, offset=offset, limit=limit)

    def list_by_actor(self, actor_id: uuid.UUID) -> list[TicketEvent]:
        stmt = (
            select(TicketEvent)
            .where(TicketEvent.actor_id == actor_id)
            .order_by(TicketEvent.created_at)
        )
        return list(self.session.scalars(stmt))


class TicketPhotoRepository(SQLAlchemyRepository[TicketPhoto]):
    model = TicketPhoto

    def list_for_ticket(self, ticket_id: uuid.UUID) -> list[TicketPhoto]:
        stmt = (
            select(TicketPhoto)
            .where(TicketPhoto.ticket_id == ticket_id)
            .order_by(TicketPhoto.created_at, TicketPhoto.id)
        )
        return list(self.session.scalars(stmt))
