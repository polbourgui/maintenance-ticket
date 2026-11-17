from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import func, select

from app.models import Role, Site, User
from app.repositories.base import SQLAlchemyRepository


class UserRepository(SQLAlchemyRepository[User]):
    model = User

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(func.lower(User.email) == email.lower()))

    def search(
        self, *, offset: int, limit: int, role: Role | None = None, site_id: uuid.UUID | None = None
    ) -> tuple[list[User], int]:
        stmt = select(User).order_by(User.created_at, User.id)
        if role is not None:
            stmt = stmt.where(User.role == role)
        if site_id is not None:
            stmt = stmt.where(User.sites.any(Site.id == site_id))
        return self._paginate(stmt, offset=offset, limit=limit)


class SiteRepository(SQLAlchemyRepository[Site]):
    model = Site

    def get_by_code(self, code: str) -> Site | None:
        return self.session.scalar(select(Site).where(Site.code == code))

    def get_many(self, ids: Iterable[uuid.UUID]) -> list[Site]:
        id_list = list(ids)
        if not id_list:
            return []
        return list(self.session.scalars(select(Site).where(Site.id.in_(id_list))))

    def search(
        self, *, offset: int, limit: int, restrict_to: set[uuid.UUID] | None
    ) -> tuple[list[Site], int]:
        stmt = select(Site).order_by(Site.name, Site.id)
        if restrict_to is not None:
            stmt = stmt.where(Site.id.in_(restrict_to))
        return self._paginate(stmt, offset=offset, limit=limit)
