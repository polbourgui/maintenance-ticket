from __future__ import annotations

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Site(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An establishment open to the public (Établissement Recevant du Public)."""

    __tablename__ = "sites"
    __table_args__ = (CheckConstraint("erp_category BETWEEN 1 AND 5", name="erp_category_range"),)

    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(255))
    postal_code: Mapped[str] = mapped_column(String(10))
    city: Mapped[str] = mapped_column(String(120))
    erp_type: Mapped[str] = mapped_column(String(4))  # e.g. "M", "N", "R", "U"
    erp_category: Mapped[int]
    is_active: Mapped[bool] = mapped_column(default=True)
