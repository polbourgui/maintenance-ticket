from __future__ import annotations

from sqlalchemy import select

from app.models import Provider
from app.repositories.base import SQLAlchemyRepository


class ProviderRepository(SQLAlchemyRepository[Provider]):
    model = Provider

    def search(self, *, offset: int, limit: int, active_only: bool) -> tuple[list[Provider], int]:
        stmt = select(Provider).order_by(Provider.company_name, Provider.id)
        if active_only:
            stmt = stmt.where(Provider.is_active.is_(True))
        return self._paginate(stmt, offset=offset, limit=limit)
