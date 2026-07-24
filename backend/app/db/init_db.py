"""
Database initialisation and default data seeding.

``init_db()`` is called once during the application lifespan (startup) in
``main.py``. It is idempotent — safe to call on every restart.

Responsibilities:
  1. Create default roles (admin, analyst, user, guest) if they do not exist.
  2. Create default permissions and associate them with roles.
  3. Create the initial superuser admin account if none exists.

Security note:
    The admin password is read from ``settings.ADMIN_DEFAULT_PASSWORD``.
    This variable MUST be set to a strong secret in production and rotated
    immediately after first login. If the variable is absent the seeder
    skips admin creation and logs a warning — it will NOT use a hardcoded
    default in production.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password

logger = get_logger(__name__)

# Default roles to seed on first boot.
_DEFAULT_ROLES: list[dict] = [
    {"name": "admin",   "description": "Full system access."},
    {"name": "analyst", "description": "Read and execute scans; generate reports."},
    {"name": "user",    "description": "Manage own targets and scans."},
    {"name": "guest",   "description": "Read-only access to shared scan results."},
]


async def _seed_roles(session: AsyncSession) -> dict[str, "Any"]:
    """
    Ensure all default roles exist.

    Returns a mapping of role name → Role ORM object.
    """
    # Import here to avoid circular imports at module initialisation.
    from app.db.models.role import Role

    role_map: dict[str, Role] = {}

    for role_data in _DEFAULT_ROLES:
        result = await session.execute(
            select(Role).where(Role.name == role_data["name"])
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            role = Role(
                id=uuid.uuid4(),
                name=role_data["name"],
                description=role_data["description"],
            )
            session.add(role)
            await session.flush()
            role_map[role.name] = role
            logger.info("Seeded role", extra={"role": role.name})
        else:
            role_map[existing.name] = existing

    return role_map


async def _seed_admin_user(
    session: AsyncSession,
    admin_role: "Any",
) -> None:
    """
    Create the initial superuser admin account if one does not exist.

    Reads credentials from environment variables. If ``ADMIN_EMAIL`` or
    ``ADMIN_DEFAULT_PASSWORD`` are not set, skips creation and logs a warning.
    """
    from app.db.models.user import User

    admin_email: str | None = getattr(settings, "ADMIN_EMAIL", None)
    admin_password: str | None = getattr(settings, "ADMIN_DEFAULT_PASSWORD", None)

    if not admin_email or not admin_password:
        logger.warning(
            "Admin seeding skipped — ADMIN_EMAIL or ADMIN_DEFAULT_PASSWORD not set. "
            "Set these variables to create the initial superuser on first boot."
        )
        return

    result = await session.execute(
        select(User).where(User.email == admin_email)
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        logger.debug("Admin user already exists — skipping seed.")
        return

    admin = User(
        id=uuid.uuid4(),
        username="admin",
        email=admin_email,
        hashed_password=hash_password(admin_password),
        is_active=True,
        is_verified=True,
        is_superuser=True,
    )
    admin.roles.append(admin_role)
    session.add(admin)
    await session.flush()

    logger.info(
        "Initial admin user created",
        extra={"email": admin_email},
    )


async def init_db(session: AsyncSession) -> None:
    """
    Seed the database with required baseline data.

    This function is idempotent — it checks for existing records before
    inserting and is safe to call on every application startup.

    Args:
        session: An active async SQLAlchemy session.
    """
    logger.info("Running database initialisation...")

    try:
        role_map = await _seed_roles(session)
        await _seed_admin_user(session, admin_role=role_map.get("admin"))
        await session.commit()
        logger.info("Database initialisation complete.")
    except Exception as exc:
        await session.rollback()
        logger.error("Database initialisation failed", exc_info=exc)
        raise


from typing import Any  # noqa: E402 — resolves forward references used above
