from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.api.deps import (
    PaginationDep,
    PhotoServiceDep,
    Policy,
    SettingsDep,
    TicketServiceDep,
    require,
)
from app.core.errors import BusinessRuleError
from app.domain.rbac import Permission
from app.models import PhotoKind, TicketPriority, TicketStatus
from app.repositories import TicketFilter
from app.schemas.common import ErrorResponse, Page
from app.schemas.tickets import (
    TicketAssignment,
    TicketCreate,
    TicketEventRead,
    TicketPhotoRead,
    TicketRead,
    TicketStatusChange,
    TicketUpdate,
)

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"description": "Validation or business-rule error"},
    },
)

_UPLOAD_CHUNK = 64 * 1024


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(body: TicketCreate, policy: Policy, tickets: TicketServiceDep) -> TicketRead:
    return TicketRead.from_entity(tickets.create(policy, body))


@router.get("", response_model=Page[TicketRead])
def list_tickets(
    policy: Policy,
    tickets: TicketServiceDep,
    page: PaginationDep,
    site_id: uuid.UUID | None = None,
    status_: Annotated[TicketStatus | None, Query(alias="status")] = None,
    priority: TicketPriority | None = None,
    technician_id: uuid.UUID | None = None,
    provider_id: uuid.UUID | None = None,
    include_archived: bool = False,
) -> Page[TicketRead]:
    filters = TicketFilter(
        site_id=site_id,
        status=status_,
        priority=priority,
        assignee_user_id=technician_id,
        assignee_provider_id=provider_id,
        include_archived=include_archived,
    )
    items, total = tickets.search(policy, filters, offset=page.offset, limit=page.limit)
    return Page(
        items=[TicketRead.from_entity(t) for t in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(ticket_id: uuid.UUID, policy: Policy, tickets: TicketServiceDep) -> TicketRead:
    return TicketRead.from_entity(tickets.get(policy, ticket_id))


@router.patch(
    "/{ticket_id}",
    response_model=TicketRead,
    dependencies=[Depends(require(Permission.TICKET_UPDATE))],
)
def update_ticket(
    ticket_id: uuid.UUID, body: TicketUpdate, policy: Policy, tickets: TicketServiceDep
) -> TicketRead:
    return TicketRead.from_entity(tickets.update(policy, ticket_id, body))


@router.put(
    "/{ticket_id}/assignment",
    response_model=TicketRead,
    dependencies=[Depends(require(Permission.TICKET_ASSIGN))],
)
def assign_ticket(
    ticket_id: uuid.UUID, body: TicketAssignment, policy: Policy, tickets: TicketServiceDep
) -> TicketRead:
    """Assign to a technician **or** an external provider (both null = unassign).
    Sends an e-mail to the assignee."""
    return TicketRead.from_entity(tickets.assign(policy, ticket_id, body))


@router.post("/{ticket_id}/status", response_model=TicketRead)
def change_status(
    ticket_id: uuid.UUID, body: TicketStatusChange, policy: Policy, tickets: TicketServiceDep
) -> TicketRead:
    """Workflow: todo → in_progress | blocked ; in_progress → todo | blocked | done ;
    blocked → todo | in_progress ; done → in_progress (admin reopen).
    Blocking requires a comment. Notifies creator & assignee by e-mail."""
    return TicketRead.from_entity(tickets.change_status(policy, ticket_id, body))


@router.post(
    "/{ticket_id}/archive",
    response_model=TicketRead,
    dependencies=[Depends(require(Permission.TICKET_ARCHIVE))],
)
def archive_ticket(ticket_id: uuid.UUID, policy: Policy, tickets: TicketServiceDep) -> TicketRead:
    """Archive a completed ticket: it becomes read-only and leaves the default listings."""
    return TicketRead.from_entity(tickets.archive(policy, ticket_id))


@router.get("/{ticket_id}/history", response_model=list[TicketEventRead])
def ticket_history(
    ticket_id: uuid.UUID, policy: Policy, tickets: TicketServiceDep
) -> list[TicketEventRead]:
    return [TicketEventRead.model_validate(e) for e in tickets.history(policy, ticket_id)]


# -- photos ----------------------------------------------------------------------------------
@router.post(
    "/{ticket_id}/photos",
    response_model=TicketPhotoRead,
    status_code=status.HTTP_201_CREATED,
    responses={413: {"model": ErrorResponse, "description": "File too large"}},
)
async def upload_photo(
    ticket_id: uuid.UUID,
    policy: Policy,
    photos: PhotoServiceDep,
    settings: SettingsDep,
    kind: Annotated[PhotoKind, Form()],
    file: Annotated[UploadFile, File(description="JPEG or PNG; EXIF/metadata are stripped")],
) -> TicketPhotoRead:
    data = bytearray()
    while chunk := await file.read(_UPLOAD_CHUNK):
        data += chunk
        if len(data) > settings.max_upload_bytes:
            raise _PayloadTooLargeError(settings.max_upload_bytes)
    photo = photos.upload(policy, ticket_id, kind, bytes(data))
    return TicketPhotoRead.model_validate(photo)


@router.get("/{ticket_id}/photos", response_model=list[TicketPhotoRead])
def list_photos(
    ticket_id: uuid.UUID, policy: Policy, photos: PhotoServiceDep
) -> list[TicketPhotoRead]:
    return [TicketPhotoRead.model_validate(p) for p in photos.search(policy, ticket_id)]


@router.get(
    "/{ticket_id}/photos/{photo_id}",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}},
)
def download_photo(
    ticket_id: uuid.UUID, photo_id: uuid.UUID, policy: Policy, photos: PhotoServiceDep
) -> Response:
    photo, content = photos.content(policy, ticket_id, photo_id)
    return Response(
        content=content,
        media_type=photo.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{photo.storage_key}"',
            "Cache-Control": "private, no-store",
        },
    )


class _PayloadTooLargeError(BusinessRuleError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    code = "payload_too_large"

    def __init__(self, limit: int) -> None:
        super().__init__(f"File exceeds the maximum size of {limit} bytes")
