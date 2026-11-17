from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.models import Role
from app.schemas.common import Phone, ReadModel, ShortText, StrictInput


class UserCreate(BaseModel):
    model_config = StrictInput
    email: EmailStr
    full_name: ShortText
    phone: Phone | None = None
    password: str = Field(max_length=128)
    role: Role
    site_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)


class UserUpdate(BaseModel):
    model_config = StrictInput
    full_name: ShortText | None = None
    phone: Phone | None = None
    role: Role | None = None
    is_active: bool | None = None
    site_ids: list[uuid.UUID] | None = Field(default=None, max_length=500)


class UserRead(BaseModel):
    model_config = ReadModel
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    role: Role
    is_active: bool
    site_ids: list[uuid.UUID]
    created_at: datetime
    last_login_at: datetime | None


class UserSummary(BaseModel):
    """Public view of a user (no contact data) shown to other users."""

    model_config = ReadModel
    id: uuid.UUID
    full_name: str


class PersonalDataExport(BaseModel):
    """GDPR art. 15 / 20: right of access and data portability."""

    generated_at: datetime
    profile: UserRead
    tickets_created: list[dict[str, Any]]
    ticket_events: list[dict[str, Any]]
    active_sessions: int
