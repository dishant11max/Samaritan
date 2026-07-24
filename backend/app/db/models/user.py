"""
User ORM model.

The ``User`` table is the central identity entity.  Every other domain
object (targets, scans, reports, audit logs) references it.

Security decisions:
  - ``hashed_password`` stores only the bcrypt hash — never the plaintext.
  - ``failed_login_attempts`` + ``locked_until`` enable brute-force lockout.
  - ``is_verified`` gates email-verified features.
  - Soft delete via ``deleted_at`` (inherited from TimestampMixin) preserves
    audit history while preventing login.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.models.associations import user_roles


class User(TimestampMixin, Base):
    """Authenticated principal of the Samaritan platform."""

    __tablename__ = "users"

    __table_args__ = (
        Index("ix_users_email_active", "email", "deleted_at"),
        Index("ix_users_username_active", "username", "deleted_at"),
    )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # ------------------------------------------------------------------
    # Account state
    # ------------------------------------------------------------------
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # ------------------------------------------------------------------
    # Brute-force protection
    # ------------------------------------------------------------------
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    roles: Mapped[list["Role"]] = relationship(  # type: ignore[name-defined]
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",  # async-safe; loaded automatically on access
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(  # type: ignore[name-defined]
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(  # type: ignore[name-defined]
        "AuditLog",
        back_populates="user",
    )
    targets: Mapped[list["Target"]] = relationship(  # type: ignore[name-defined]
        "Target",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    scans: Mapped[list["Scan"]] = relationship(  # type: ignore[name-defined]
        "Scan",
        back_populates="creator",
        foreign_keys="[Scan.created_by]",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
