"""User repository — data access layer for the User model."""

from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.user import User
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a non-deleted user by email address (case-insensitive)."""
        result = await self.session.execute(
            select(User)
            .where(
                User.email == email.lower().strip(),
                User.deleted_at.is_(None),
            )
            .options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Fetch a non-deleted user by username."""
        result = await self.session.execute(
            select(User)
            .where(
                User.username == username.strip(),
                User.deleted_at.is_(None),
            )
            .options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Fetch a non-deleted user by UUID, eagerly loading roles."""
        result = await self.session.execute(
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Return True if a non-deleted account with this email exists."""
        return await self.get_by_email(email) is not None

    async def username_exists(self, username: str) -> bool:
        """Return True if a non-deleted account with this username exists."""
        return await self.get_by_username(username) is not None

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 20,
        is_active: bool | None = None,
    ) -> tuple[Sequence[User], int]:
        """
        Return a page of users and the total count.

        Returns:
            A (users, total) tuple.
        """
        filters = []
        if is_active is not None:
            filters.append(User.is_active == is_active)

        users = await self.get_all(skip=skip, limit=limit, filters=filters or None)
        total = await self.count(filters=filters or None)
        return users, total

    async def increment_failed_attempts(self, user: User) -> User:
        """Increment the brute-force login attempt counter."""
        return await self.update(
            user, failed_login_attempts=user.failed_login_attempts + 1
        )

    async def reset_failed_attempts(self, user: User) -> User:
        """Reset the brute-force counter after a successful login."""
        return await self.update(
            user,
            failed_login_attempts=0,
            locked_until=None,
        )
