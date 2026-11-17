from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.base import Base


class SQLAlchemyRepository[ModelT: Base]:
    """Generic persistence operations. Concrete repositories add domain-specific queries.

    Repositories never commit: transaction boundaries belong to the Unit of Work.
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, entity_id: uuid.UUID) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def _paginate(
        self, stmt: Select[ModelT], *, offset: int, limit: int
    ) -> tuple[list[ModelT], int]:
        count_stmt: Select[Any] = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = self.session.scalar(count_stmt) or 0
        items = list(self.session.scalars(stmt.offset(offset).limit(limit)).unique())
        return items, total
