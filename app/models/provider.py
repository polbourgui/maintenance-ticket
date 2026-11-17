from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Provider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """External contractor (prestataire) that can be assigned to tickets."""

    __tablename__ = "providers"

    company_name: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(32))
    specialty: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(default=True)
