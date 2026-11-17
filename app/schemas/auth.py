from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import StrictInput


class TokenPair(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime


class RefreshRequest(BaseModel):
    model_config = StrictInput
    refresh_token: str = Field(min_length=20, max_length=200)


class PasswordChange(BaseModel):
    model_config = StrictInput
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)
