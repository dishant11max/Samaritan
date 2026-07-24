"""
ScanResult ORM model.

Each ``ScanResult`` represents a single finding discovered during a scan —
a vulnerability, open port, misconfiguration, or informational finding.

CVSS alignment:
  - ``cvss_score``:  base score (0.0–10.0, one decimal place).
  - ``cvss_vector``: full CVSS v3.1 vector string for tooling integration.
  - ``severity``:    derived from score but stored independently to allow
                     analyst override without changing the raw score.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import SeverityLevel
from app.db.base import Base, TimestampMixin


class ScanResult(TimestampMixin, Base):
    """A single vulnerability or informational finding from a scan."""

    __tablename__ = "scan_results"

    __table_args__ = (
        Index("ix_scan_results_scan_id", "scan_id"),
        Index("ix_scan_results_severity", "severity"),
        Index("ix_scan_results_false_positive", "false_positive"),
    )

    # Parent scan
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Finding identity
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Severity classification
    severity: Mapped[SeverityLevel] = mapped_column(
        SAEnum(SeverityLevel, name="severity_level_enum", create_constraint=True),
        nullable=False,
        default=SeverityLevel.NONE,
    )
    cvss_score: Mapped[float | None] = mapped_column(
        Numeric(4, 1), nullable=True, default=None  # e.g. 9.8, 7.2
    )
    cvss_vector: Mapped[str | None] = mapped_column(
        String(200), nullable=True, default=None  # CVSS:3.1/AV:N/AC:L/...
    )

    # Network context
    port: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    protocol: Mapped[str | None] = mapped_column(String(10), nullable=True, default=None)
    service: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)

    # Evidence and remediation
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    # CVE references — stored as a JSONB list, e.g. ["CVE-2023-1234", ...]
    cve_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=None)

    # Analyst review
    false_positive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Relationships
    scan: Mapped["Scan"] = relationship(  # type: ignore[name-defined]
        "Scan",
        back_populates="results",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<ScanResult title={self.title!r} severity={self.severity}>"
