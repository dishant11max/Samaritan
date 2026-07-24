"""
FastAPI dependency injection providers for Samaritan.

All dependencies in this module follow FastAPI's ``Depends()`` pattern.
They are the authorised entry points for acquiring shared resources
(database sessions, Redis connections, authenticated users) inside routes
and controllers.

Security note:
    ``get_current_user`` and its derivatives are the enforcement boundary
    for authentication. Every protected endpoint MUST depend on one of them.
    Never extract or validate a JWT inside a route function directly.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.logging import get_logger

logger = get_logger(__name__)

# OAuth2 scheme — tells FastAPI where to extract the Bearer token.
# ``tokenUrl`` points at the login endpoint so Swagger's "Authorize" button works.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,  # We raise a typed exception ourselves, not FastAPI's default.
)


# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------


async def get_db() -> AsyncSession:  # type: ignore[return]
    """
    Yield an async SQLAlchemy session for a single request lifecycle.

    The session is committed on success and rolled back on any exception.
    FastAPI's dependency system closes it automatically after the response.

    Yields:
        An :class:`~sqlalchemy.ext.asyncio.AsyncSession` bound to the request.
    """
    # Import here to avoid circular imports at module load time.
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Redis connection
# ---------------------------------------------------------------------------


async def get_redis() -> aioredis.Redis:  # type: ignore[return]
    """
    Yield an async Redis connection from the shared connection pool.

    The pool is initialised at application startup (see ``main.py``).
    Each request borrows a connection and returns it automatically.

    Yields:
        An :class:`redis.asyncio.Redis` client instance.
    """
    from app.db.session import redis_pool

    client: aioredis.Redis = aioredis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# Authenticated user extraction
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> "Any":  # Returns app.db.models.user.User — forward ref avoids circular import
    """
    Validate the Bearer JWT and return the corresponding User ORM object.

    Steps:
        1. Ensure a token was provided.
        2. Decode and validate the JWT (signature, expiry, type claim).
        3. Load the user from the database by subject (UUID).
        4. Verify the user is active and not soft-deleted.

    Args:
        request: The current HTTP request (used for logging context).
        token:   Bearer token extracted from the ``Authorization`` header.
        db:      Injected async database session.

    Returns:
        The authenticated :class:`~app.db.models.user.User` ORM instance.

    Raises:
        AuthenticationError: If the token is missing, invalid, or the user
                             does not exist / is inactive.
    """
    from app.auth.jwt import decode_token
    from app.core.constants import TokenType
    from app.repositories.user_repository import UserRepository

    if not token:
        raise AuthenticationError("No authentication token provided.")

    payload = decode_token(token, expected_type=TokenType.ACCESS)
    user_id_str: str | None = payload.sub

    if not user_id_str:
        raise AuthenticationError("Token subject is missing.")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise AuthenticationError("Token contains an invalid user identifier.")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)

    if user is None:
        logger.warning("JWT references non-existent user", extra={"user_id": user_id_str})
        raise AuthenticationError("User account not found.")

    if not user.is_active:
        raise AuthenticationError("User account is deactivated.")

    if user.deleted_at is not None:
        raise AuthenticationError("User account no longer exists.")

    return user


async def get_current_active_user(
    current_user: Annotated["Any", Depends(get_current_user)],
) -> "Any":
    """
    Return the current user, enforcing that the account is active.

    This is a semantic alias over ``get_current_user`` for use in routes
    where the distinction between "authenticated" and "active" matters
    explicitly in the function signature.
    """
    return current_user


# ---------------------------------------------------------------------------
# RBAC role enforcement
# ---------------------------------------------------------------------------


def require_roles(*roles: str):
    """
    Return a FastAPI dependency that enforces one of the specified roles.

    Usage in a route::

        @router.get("/admin-only")
        async def admin_endpoint(
            _: Annotated[User, Depends(require_roles("admin"))]
        ):
            ...

    Args:
        *roles: One or more role names (from ``UserRole`` enum values).

    Returns:
        A FastAPI dependency callable.

    Raises:
        AuthorizationError: If the authenticated user does not hold any of
                            the required roles.
    """

    async def _check_roles(
        current_user: Annotated["Any", Depends(get_current_user)],
    ) -> "Any":
        user_role_names = {r.name for r in current_user.roles}
        if not user_role_names.intersection(set(roles)):
            logger.warning(
                "Access denied — insufficient role",
                extra={
                    "user_id": str(current_user.id),
                    "required_roles": list(roles),
                    "user_roles": list(user_role_names),
                },
            )
            raise AuthorizationError()
        return current_user

    return _check_roles


# ---------------------------------------------------------------------------
# Type aliases for route signatures (improves readability)
# ---------------------------------------------------------------------------

from typing import Any  # noqa: E402 — must be after forward refs above

DBDep = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]
CurrentUserDep = Annotated[Any, Depends(get_current_user)]
ActiveUserDep = Annotated[Any, Depends(get_current_active_user)]
