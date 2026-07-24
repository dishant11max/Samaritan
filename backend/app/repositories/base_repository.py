"""
Generic base repository with common CRUD operations.

All domain repositories extend ``BaseRepository[ModelT]``.  This removes
boilerplate and ensures consistent soft-delete filtering, pagination, and
error handling across every data access class.

Design:
  - All public methods are async.
  - Soft deletes are enforced by default (``deleted_at IS NULL``).
  - Hard deletes are explicit and only available via ``hard_delete()``.
  - Every method uses parameterised SQLAlchemy expressions — no raw SQL.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Generic async repository providing standard CRUD operations.

    Type-parameterised over a SQLAlchemy ORM model.  Subclasses set
    ``model`` at class level, e.g.::

        class UserRepository(BaseRepository[User]):
            model = User
    """

    model: Type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, record_id: uuid.UUID) -> ModelT | None:
        """Fetch a non-deleted record by its UUID primary key."""
        result = await self.session.execute(
            select(self.model).where(
                self.model.id == record_id,
                self.model.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        filters: list[Any] | None = None,
    ) -> Sequence[ModelT]:
        """
        Return a paginated list of non-deleted records.

        Args:
            skip:    Number of records to skip (offset).
            limit:   Maximum number of records to return.
            filters: Additional SQLAlchemy filter clauses.
        """
        query = select(self.model).where(self.model.deleted_at.is_(None))
        if filters:
            query = query.where(*filters)
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count(self, filters: list[Any] | None = None) -> int:
        """Return total count of non-deleted records matching optional filters."""
        query = select(func.count()).select_from(self.model).where(
            self.model.deleted_at.is_(None)
        )
        if filters:
            query = query.where(*filters)
        result = await self.session.execute(query)
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(self, **kwargs: Any) -> ModelT:
        """
        Instantiate and persist a new record.

        The session is flushed (not committed) so the record gets its
        database-generated defaults (e.g. server_default timestamps) without
        ending the transaction.
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, instance: ModelT, **kwargs: Any) -> ModelT:
        """
        Apply attribute updates to an existing ORM instance and flush.

        Args:
            instance: The loaded ORM object to update.
            **kwargs: Attribute name → new value pairs.
        """
        for key, value in kwargs.items():
            setattr(instance, key, value)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def soft_delete(self, instance: ModelT) -> ModelT:
        """
        Mark a record as deleted by setting ``deleted_at`` to now (UTC).

        The row is NOT removed from the database.  All ``get_*`` methods
        automatically exclude soft-deleted records.
        """
        instance.deleted_at = datetime.now(tz=timezone.utc)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def hard_delete(self, instance: ModelT) -> None:
        """
        Physically remove a record from the database.

        Use sparingly — prefer soft delete to preserve audit history.
        """
        await self.session.delete(instance)
        await self.session.flush()
