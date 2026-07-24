"""
Scan ORM model.

A ``Scan`` represents a single execution of a scanner against a ``Target``.
It is the central entity linking targets, results, and reports.

Lifecycle:
  PENDING → QUEUED (Celery task accepted) → RUNNING → COMPLETED | FAILED | CANCELLED

``celery_task_id`` ties the row to the background worker process for
status polling and cancellation.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ScanStatus, ScanType
from app.db.base import Base, TimestampMixin


class Scan(TimestampMixin, Base):
    """A single scanner execution against a Target."""

    __tablename__ = "scans"

    __table_args__ = (
        Index("ix_scans_target_id", "target_id"),
        Index("ix_scans_created_by", "created_by"),
        Index("ix_scans_status", "status"),
        Index("ix_scans_celery_task_id", "celery_task_id"),
    )

    # Foreign keys
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # Scan configuration
    scan_type: Mapped[ScanType] = mapped_column(
        SAEnum(ScanType, name="scan_type_enum", create_constraint=True),
        nullable=False,
    )
    scan_options: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)

    # State machine
    status: Mapped[ScanStatus] = mapped_column(
        SAEnum(ScanStatus, name="scan_status_enum", create_constraint=True),
        nullable=False,
        default=ScanStatus.PENDING,
        server_default=ScanStatus.PENDING.name,
    )
    celery_task_id: Mapped[str | None] = mapped_column(
        String(155), nullable=True, default=None
    )

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Relationships
    target: Mapped["Target"] = relationship(  # type: ignore[name-defined]
        "Target",
        back_populates="scans",
        lazy="joined",
    )
    creator: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User",
        back_populates="scans",
        foreign_keys=[created_by],
        lazy="joined",
    )
    results: Mapped[list["ScanResult"]] = relationship(  # type: ignore[name-defined]
        "ScanResult",
        back_populates="scan",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["Report"]] = relationship(  # type: ignore[name-defined]
        "Report",
        back_populates="scan",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Scan id={self.id} type={self.scan_type} status={self.status}>"
