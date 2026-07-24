"""
Target ORM model.

A ``Target`` represents a host or network endpoint that the platform
is authorised to scan.  Each target is owned by a user and may have
multiple scans associated with it over time.

Security consideration:
  - ``host`` accepts both IP addresses and hostnames.  Path traversal and
    SSRF validation must be enforced at the service layer before any
    scan is initiated — this model stores the value as-is.
  - ``is_active = False`` disables a target without removing scan history.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Target(TimestampMixin, Base):
    """A scannable host or network endpoint owned by a user."""

    __tablename__ = "targets"

    __table_args__ = (
        Index("ix_targets_owner_id", "owner_id"),
        Index("ix_targets_host", "host"),
        Index("ix_targets_is_active", "is_active"),
    )

    # Ownership
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Target identity
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    host: Mapped[str] = mapped_column(String(253), nullable=False)  # max FQDN length
    port_range: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default=None  # e.g. "80,443" or "1-65535"
    )

    # Metadata
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # Relationships
    owner: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User",
        back_populates="targets",
        lazy="joined",
    )
    scans: Mapped[list["Scan"]] = relationship(  # type: ignore[name-defined]
        "Scan",
        back_populates="target",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Target name={self.name!r} host={self.host!r}>"
