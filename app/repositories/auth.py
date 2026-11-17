from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update

from app.models import RefreshToken
from app.repositories.base import SQLAlchemyRepository


class RefreshTokenRepository(SQLAlchemyRepository[RefreshToken]):
    model = RefreshToken

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )

    def revoke_family(self, family_id: uuid.UUID, now: datetime) -> None:
        self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    def revoke_all_for_user(self, user_id: uuid.UUID, now: datetime) -> None:
        self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    def count_active_for_user(self, user_id: uuid.UUID, now: datetime) -> int:
        return len(
            list(
                self.session.scalars(
                    select(RefreshToken.id).where(
                        RefreshToken.user_id == user_id,
                        RefreshToken.revoked_at.is_(None),
                        RefreshToken.expires_at > now,
                    )
                )
            )
        )
