from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import Phone, ReadModel, ShortText, StrictInput


class ProviderCreate(BaseModel):
    model_config = StrictInput
    company_name: str = Field(min_length=2, max_length=200)
    contact_name: ShortText | None = None
    email: EmailStr
    phone: Phone | None = None
    specialty: ShortText | None = None


class ProviderUpdate(BaseModel):
    model_config = StrictInput
    company_name: str | None = Field(default=None, min_length=2, max_length=200)
    contact_name: ShortText | None = None
    email: EmailStr | None = None
    phone: Phone | None = None
    specialty: ShortText | None = None
    is_active: bool | None = None


class ProviderRead(BaseModel):
    model_config = ReadModel
    id: uuid.UUID
    company_name: str
    contact_name: str | None
    email: str
    phone: str | None
    specialty: str | None
    is_active: bool
    created_at: datetime
