from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from app.models import (
    AssigneeType,
    PhotoKind,
    Ticket,
    TicketEventType,
    TicketPriority,
    TicketStatus,
)
from app.schemas.common import ReadModel, StrictInput


class TicketLocation(BaseModel):
    model_config = StrictInput
    building: str | None = Field(default=None, max_length=120, examples=["Bâtiment A"])
    floor: str | None = Field(default=None, max_length=32, examples=["R+1"])
    room: str = Field(min_length=1, max_length=120, examples=["Local technique CTA"])
    details: str | None = Field(default=None, max_length=500, examples=["Trappe au plafond"])


class TicketCreate(BaseModel):
    model_config = StrictInput
    site_id: uuid.UUID
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    priority: TicketPriority = TicketPriority.MEDIUM
    location: TicketLocation


class TicketUpdate(BaseModel):
    model_config = StrictInput
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10_000)
    priority: TicketPriority | None = None
    location: TicketLocation | None = None


class TicketAssignment(BaseModel):
    """Assign to an internal technician *or* an external provider. Both null = unassign."""

    model_config = StrictInput
    technician_id: uuid.UUID | None = None
    provider_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _at_most_one(self) -> Self:
        if self.technician_id is not None and self.provider_id is not None:
            raise ValueError("Provide either technician_id or provider_id, not both")
        return self


class TicketStatusChange(BaseModel):
    model_config = StrictInput
    status: TicketStatus
    comment: str | None = Field(default=None, max_length=2000)


class AssigneeRead(BaseModel):
    type: AssigneeType
    id: uuid.UUID
    display_name: str


class TicketRead(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    title: str
    description: str
    priority: TicketPriority
    status: TicketStatus
    location: TicketLocation
    created_by_id: uuid.UUID
    created_by_name: str
    assignee: AssigneeRead | None
    started_at: datetime | None
    closed_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, ticket: Ticket) -> TicketRead:
        assignee: AssigneeRead | None = None
        if ticket.assignee_user is not None:
            assignee = AssigneeRead(
                type=AssigneeType.TECHNICIAN,
                id=ticket.assignee_user.id,
                display_name=ticket.assignee_user.full_name,
            )
        elif ticket.assignee_provider is not None:
            assignee = AssigneeRead(
                type=AssigneeType.PROVIDER,
                id=ticket.assignee_provider.id,
                display_name=ticket.assignee_provider.company_name,
            )
        return cls(
            id=ticket.id,
            site_id=ticket.site_id,
            title=ticket.title,
            description=ticket.description,
            priority=ticket.priority,
            status=ticket.status,
            location=TicketLocation(
                building=ticket.location_building,
                floor=ticket.location_floor,
                room=ticket.location_room,
                details=ticket.location_details,
            ),
            created_by_id=ticket.created_by_id,
            created_by_name=ticket.created_by.full_name,
            assignee=assignee,
            started_at=ticket.started_at,
            closed_at=ticket.closed_at,
            archived_at=ticket.archived_at,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
        )


class TicketEventRead(BaseModel):
    model_config = ReadModel
    id: uuid.UUID
    ticket_id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_name: str | None
    event_type: TicketEventType
    from_status: TicketStatus | None
    to_status: TicketStatus | None
    comment: str | None
    details: dict[str, Any]
    created_at: datetime


class TicketPhotoRead(BaseModel):
    model_config = ReadModel
    id: uuid.UUID
    ticket_id: uuid.UUID
    kind: PhotoKind
    content_type: str
    size_bytes: int
    sha256: str
    uploaded_by_id: uuid.UUID
    created_at: datetime
