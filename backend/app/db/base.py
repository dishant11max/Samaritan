"""
SQLAlchemy declarative base and shared ORM mixins.

All database models must extend ``Base`` and include ``TimestampMixin``.
The mixin provides:
  - UUID primary key (Python-generated, not database-generated, for
    portability across all PostgreSQL versions without extensions).
  - ``created_at`` / ``updated_at`` timestamps (UTC, managed automatically).
  - ``deleted_at`` nullable timestamp for soft deletes.
  - ``is_deleted`` Python property for convenience checks.

Design decision — UUIDs over integers:
    UUIDs as primary keys prevent enumeration attacks (sequential integer
    IDs reveal record counts and allow resource traversal). The trade-off
    is slightly larger index sizes, which is acceptable for this scale.

Design decision — soft deletes:
    Setting ``deleted_at`` rather than physically deleting rows preserves
    audit history, simplifies foreign key integrity, and allows recovery.
    All repository queries MUST filter ``deleted_at IS NULL`` by default.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(tz=timezone.utc)


class Base(DeclarativeBase):
    """
    Shared declarative base for all Samaritan ORM models.

    Import this base in every model module and register it in
    ``app/db/models/__init__.py`` so Alembic's autogenerate sees all tables.
    """
    pass


class TimestampMixin:
    """
    Mixin that adds UUID primary key and standard audit timestamps.

    Attributes:
        id:         UUID v4 primary key, generated in Python on insert.
        created_at: UTC datetime of record creation (server sets on insert).
        updated_at: UTC datetime of last modification (auto-updated on change).
        deleted_at: UTC datetime of soft deletion; ``None`` when not deleted.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,  # Index improves soft-delete filter performance at scale.
    )

    @property
    def is_deleted(self) -> bool:
        """Return ``True`` when this record has been soft-deleted."""
        return self.deleted_at is not None
