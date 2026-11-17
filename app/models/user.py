from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.enums import Role

if TYPE_CHECKING:
    from app.models.site import Site

site_memberships = Table(
    "site_memberships",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("site_id", ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True),
)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(32))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(str_enum(Role))
    is_active: Mapped[bool] = mapped_column(default=True)
    # Incremented to invalidate every access token issued before (logout-all, password change).
    token_version: Mapped[int] = mapped_column(default=0)
    last_login_at: Mapped[datetime | None]
    anonymized_at: Mapped[datetime | None]

    sites: Mapped[list[Site]] = relationship(secondary=site_memberships, lazy="selectin")

    @property
    def site_ids(self) -> set[uuid.UUID]:
        return {site.id for site in self.sites}
