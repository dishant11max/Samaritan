"""
RefreshToken ORM model.

Security design:
  - The raw token string is NEVER stored. Only a SHA-256 hex digest is
    persisted, so a database breach cannot be used to replay sessions.
  - ``family_id`` supports token-rotation families: when a refresh token
    is used to issue a new one, the old token is revoked. If the old token
    is presented again (replay attack), the entire family is revoked.
  - ``ip_address`` and ``user_agent`` provide audit context for suspicious
    refresh activity.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class RefreshToken(TimestampMixin, Base):
    """Persisted refresh token record (stores hash only, never raw token)."""

    __tablename__ = "refresh_tokens"

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_family_id", "family_id"),
        Index("ix_refresh_tokens_revoked_at", "revoked_at"),
    )

    # Owner
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Token identity — SHA-256(raw_token), hex-encoded
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )

    # Rotation family — all tokens in a family share this ID.
    # Replaying a revoked token from a family revokes the whole family.
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, default=uuid.uuid4
    )

    # Lifecycle
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Audit context
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User",
        back_populates="refresh_tokens",
        lazy="joined",
    )

    @property
    def is_revoked(self) -> bool:
        """Return ``True`` if this token has been explicitly revoked."""
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        """Return ``True`` if the token's expiry time has passed."""
        from datetime import timezone
        from datetime import datetime as dt
        return dt.now(tz=timezone.utc) >= self.expires_at

    @property
    def is_valid(self) -> bool:
        """Return ``True`` only if the token is neither revoked nor expired."""
        return not self.is_revoked and not self.is_expired

    def __repr__(self) -> str:
        return f"<RefreshToken user_id={self.user_id} revoked={self.is_revoked}>"
