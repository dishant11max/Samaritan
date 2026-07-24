"""
AuditLog ORM model.

The audit log is an append-only table recording every security-relevant
event in the system.  Rows should NEVER be updated or hard-deleted —
the repository layer enforces this.

Design decisions:
  - ``user_id`` is nullable to capture events from unauthenticated requests
    (e.g. failed login attempts, rate-limit hits).
  - ``old_value`` / ``new_value`` store JSON snapshots for change tracking
    on sensitive resources (user updates, role assignments, etc.).
  - No ``updated_at`` trigger is meaningful here; TimestampMixin provides
    the field but the repository must never issue UPDATE statements.
  - No soft delete — audit logs must be immutable once written.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AuditEventType, AuditStatus
from app.db.base import Base, TimestampMixin


class AuditLog(TimestampMixin, Base):
    """Immutable record of a security-relevant platform event."""

    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_event_type", "event_type"),
        Index("ix_audit_logs_resource_type", "resource_type"),
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_status", "status"),
    )

    # Actor (nullable — unauthenticated events have no user)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )

    # Event classification
    event_type: Mapped[AuditEventType] = mapped_column(
        SAEnum(AuditEventType, name="audit_event_type_enum", create_constraint=True),
        nullable=False,
    )
    status: Mapped[AuditStatus] = mapped_column(
        SAEnum(AuditStatus, name="audit_status_enum", create_constraint=True),
        nullable=False,
        default=AuditStatus.SUCCESS,
    )

    # Resource context
    resource_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, default=None  # UUID as string
    )

    # Request context
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Change data capture (for sensitive resource mutations)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)

    # Relationships
    user: Mapped["User | None"] = relationship(  # type: ignore[name-defined]
        "User",
        back_populates="audit_logs",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog event={self.event_type} "
            f"user_id={self.user_id} status={self.status}>"
        )
