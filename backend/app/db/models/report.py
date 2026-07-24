"""
Report ORM model.

A ``Report`` is generated from a completed scan and summarises the findings
in a chosen format (PDF, JSON, HTML, CSV).

``file_path`` stores the path to the generated file on the server filesystem
or object storage.  It must be treated as sensitive — path traversal checks
are enforced at the service layer before serving the file.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ReportFormat
from app.db.base import Base, TimestampMixin


class Report(TimestampMixin, Base):
    """A generated vulnerability report derived from a completed scan."""

    __tablename__ = "reports"

    __table_args__ = (
        Index("ix_reports_scan_id", "scan_id"),
        Index("ix_reports_generated_by", "generated_by"),
        Index("ix_reports_is_public", "is_public"),
    )

    # References
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
    )
    generated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # Content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    # Output
    format: Mapped[ReportFormat] = mapped_column(
        SAEnum(ReportFormat, name="report_format_enum", create_constraint=True),
        nullable=False,
        default=ReportFormat.JSON,
    )
    file_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, default=None
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Relationships
    scan: Mapped["Scan"] = relationship(  # type: ignore[name-defined]
        "Scan",
        back_populates="reports",
        lazy="joined",
    )
    generator: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User",
        foreign_keys=[generated_by],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Report title={self.title!r} format={self.format}>"
