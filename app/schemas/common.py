from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# Input models reject unknown fields: prevents mass-assignment (e.g. sending "role": "admin").
StrictInput = ConfigDict(extra="forbid", str_strip_whitespace=True)
ReadModel = ConfigDict(from_attributes=True)

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Phone = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9 .\-()]{6,32}$", max_length=32)
]


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class ErrorResponse(BaseModel):
    code: str
    detail: str
