from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.common import ReadModel, StrictInput

SiteCode = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9_-]{2,32}$")
]
ErpType = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z]{1,4}$")
]


class SiteCreate(BaseModel):
    model_config = StrictInput
    code: SiteCode
    name: str = Field(min_length=2, max_length=200)
    address: str = Field(min_length=2, max_length=255)
    postal_code: str = Field(pattern=r"^[0-9A-Za-z -]{3,10}$")
    city: str = Field(min_length=1, max_length=120)
    erp_type: ErpType = Field(
        description="Type d'ERP (J, L, M, N, O, P, R, S, T, U, V, W, X, Y...)"
    )
    erp_category: int = Field(ge=1, le=5, description="Catégorie ERP (1 à 5)")


class SiteUpdate(BaseModel):
    model_config = StrictInput
    name: str | None = Field(default=None, min_length=2, max_length=200)
    address: str | None = Field(default=None, min_length=2, max_length=255)
    postal_code: str | None = Field(default=None, pattern=r"^[0-9A-Za-z -]{3,10}$")
    city: str | None = Field(default=None, min_length=1, max_length=120)
    erp_type: ErpType | None = None
    erp_category: int | None = Field(default=None, ge=1, le=5)
    is_active: bool | None = None


class SiteRead(BaseModel):
    model_config = ReadModel
    id: uuid.UUID
    code: str
    name: str
    address: str
    postal_code: str
    city: str
    erp_type: str
    erp_category: int
    is_active: bool
    created_at: datetime


class MembershipRequest(BaseModel):
    model_config = StrictInput
    user_id: uuid.UUID
