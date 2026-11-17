from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.db.types import utcnow


class RefreshToken(UUIDPrimaryKeyMixin, Base):
    """Server-side session. Only the SHA-256 of the token is stored.

    Tokens are rotated on every use; all tokens of a rotation chain share a ``family_id`` so that
    re-use of an already-rotated token (theft indicator) revokes the whole family.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
