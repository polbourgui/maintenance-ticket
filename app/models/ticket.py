from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.db.types import utcnow
from app.models.enums import AssigneeType, PhotoKind, TicketEventType, TicketPriority, TicketStatus
from app.models.provider import Provider
from app.models.site import Site
from app.models.user import User


class Ticket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "NOT (assignee_user_id IS NOT NULL AND assignee_provider_id IS NOT NULL)",
            name="single_assignee",
        ),
        Index("ix_tickets_site_status", "site_id", "status"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[TicketPriority] = mapped_column(str_enum(TicketPriority))
    status: Mapped[TicketStatus] = mapped_column(str_enum(TicketStatus), default=TicketStatus.TODO)

    location_building: Mapped[str | None] = mapped_column(String(120))
    location_floor: Mapped[str | None] = mapped_column(String(32))
    location_room: Mapped[str] = mapped_column(String(120))
    location_details: Mapped[str | None] = mapped_column(String(500))

    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    assignee_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("providers.id", ondelete="RESTRICT"), index=True
    )

    started_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
    archived_at: Mapped[datetime | None]
    # Optimistic locking: concurrent updates of the same ticket raise StaleDataError (-> 409).
    version: Mapped[int] = mapped_column(default=1)

    site: Mapped[Site] = relationship(lazy="joined")
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id], lazy="joined")
    assignee_user: Mapped[User | None] = relationship(
        foreign_keys=[assignee_user_id], lazy="joined"
    )
    assignee_provider: Mapped[Provider | None] = relationship(lazy="joined")

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012

    @property
    def assignee_type(self) -> AssigneeType | None:
        if self.assignee_user_id is not None:
            return AssigneeType.TECHNICIAN
        if self.assignee_provider_id is not None:
            return AssigneeType.PROVIDER
        return None

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


class TicketEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only audit trail of everything that happened to a ticket."""

    __tablename__ = "ticket_events"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="RESTRICT"), index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    event_type: Mapped[TicketEventType] = mapped_column(str_enum(TicketEventType))
    from_status: Mapped[TicketStatus | None] = mapped_column(str_enum(TicketStatus))
    to_status: Mapped[TicketStatus | None] = mapped_column(str_enum(TicketStatus))
    comment: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


class TicketPhoto(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ticket_photos"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[PhotoKind] = mapped_column(str_enum(PhotoKind))
    storage_key: Mapped[str] = mapped_column(String(128), unique=True)
    content_type: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
