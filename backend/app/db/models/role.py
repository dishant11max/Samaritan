"""
Role and Permission ORM models.

Implements a flat RBAC model:
  - ``Role``       — a named collection of permissions (admin, analyst, user, guest).
  - ``Permission`` — a single resource+action pair (e.g. scan:execute).

The M2M junction tables (user_roles, role_permissions) live in
``app.db.models.associations`` to avoid circular imports.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.models.associations import role_permissions, user_roles


class Role(TimestampMixin, Base):
    """A named role that carries a set of permissions."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    users: Mapped[list["User"]] = relationship(  # type: ignore[name-defined]
        "User",
        secondary=user_roles,
        back_populates="roles",
    )
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Role name={self.name!r}>"


class Permission(TimestampMixin, Base):
    """
    A discrete permission granting a specific action on a specific resource.

    Example: resource="scan", action="execute" → allows running scans.
    """

    __tablename__ = "permissions"

    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resource: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions",
    )

    def __repr__(self) -> str:
        return f"<Permission {self.resource}:{self.action}>"
