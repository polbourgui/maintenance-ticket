from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar

from sqlalchemy import Enum, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.types import UTCDateTime, utcnow

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: UTCDateTime()}


def str_enum(enum_cls: type[StrEnum]) -> Enum:
    """Store enums by value as VARCHAR + CHECK constraint (portable, migration-friendly)."""
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda members: [m.value for m in members],
        name=enum_cls.__name__.lower(),
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
