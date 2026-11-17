from __future__ import annotations

import hashlib
import uuid

from app.core.errors import BusinessRuleError, NotFoundError
from app.domain.rbac import AccessPolicy, Permission
from app.models import PhotoKind, TicketEventType, TicketPhoto
from app.services.tickets import TicketService
from app.storage import FileStorage, ImageValidationError, sanitize_image

MAX_PHOTOS_PER_TICKET = 30


class PhotoService:
    def __init__(self, tickets: TicketService, storage: FileStorage) -> None:
        self.tickets = tickets
        self.uow = tickets.uow
        self.storage = storage

    def upload(
        self, policy: AccessPolicy, ticket_id: uuid.UUID, kind: PhotoKind, data: bytes
    ) -> TicketPhoto:
        policy.require(Permission.PHOTO_UPLOAD)
        ticket = self.tickets.get(policy, ticket_id)
        if ticket.is_archived:
            raise BusinessRuleError("Archived tickets are read-only")
        if len(self.uow.ticket_photos.list_for_ticket(ticket.id)) >= MAX_PHOTOS_PER_TICKET:
            raise BusinessRuleError(
                f"A ticket cannot hold more than {MAX_PHOTOS_PER_TICKET} photos"
            )
        try:
            image = sanitize_image(data)
        except ImageValidationError as exc:
            raise BusinessRuleError(str(exc)) from exc

        key = f"{uuid.uuid4().hex}.{image.extension}"
        photo = TicketPhoto(
            ticket_id=ticket.id,
            kind=kind,
            storage_key=key,
            content_type=image.content_type,
            size_bytes=len(image.data),
            sha256=hashlib.sha256(image.data).hexdigest(),
            uploaded_by_id=policy.user.id,
        )
        self.storage.save(key, image.data)
        try:
            self.uow.ticket_photos.add(photo)
            self.tickets.record_event(
                ticket,
                policy.user,
                TicketEventType.PHOTO_ADDED,
                {"photo_id": str(photo.id), "kind": kind.value},
            )
            self.uow.commit()
        except Exception:
            self.uow.rollback()
            self.storage.delete(key)  # no orphan file if the DB transaction fails
            raise
        return photo

    def search(self, policy: AccessPolicy, ticket_id: uuid.UUID) -> list[TicketPhoto]:
        policy.require(Permission.PHOTO_READ)
        ticket = self.tickets.get(policy, ticket_id)
        return self.uow.ticket_photos.list_for_ticket(ticket.id)

    def content(
        self, policy: AccessPolicy, ticket_id: uuid.UUID, photo_id: uuid.UUID
    ) -> tuple[TicketPhoto, bytes]:
        policy.require(Permission.PHOTO_READ)
        ticket = self.tickets.get(policy, ticket_id)
        photo = self.uow.ticket_photos.get(photo_id)
        if photo is None or photo.ticket_id != ticket.id:
            raise NotFoundError("Photo not found")
        return photo, self.storage.read(photo.storage_key)
