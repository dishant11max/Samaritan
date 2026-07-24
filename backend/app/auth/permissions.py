"""
FastAPI dependency factories for permission-based access control.

Complements the role-based matrix in ``roles.py`` with route-level
permission enforcement via ``Depends()``.

Usage::

    from app.auth.permissions import require_permission
    from app.core.constants import Resource, Action

    @router.post("/scans")
    async def create_scan(
        _: Annotated[User, Depends(require_permission(Resource.SCAN, Action.CREATE))],
        ...
    ):
        ...
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends

from app.auth.roles import user_has_permission
from app.core.constants import Action, Resource
from app.core.dependencies import get_current_user
from app.core.exceptions import AuthorizationError
from app.core.logging import get_logger

logger = get_logger(__name__)


def require_permission(resource: Resource, action: Action):
    """
    Return a FastAPI dependency that enforces a specific RBAC permission.

    The dependency resolves the current authenticated user, extracts their
    role names, and checks them against the ``ROLE_PERMISSIONS`` matrix.

    Args:
        resource: The resource being accessed (e.g. ``Resource.SCAN``).
        action:   The action being performed (e.g. ``Action.EXECUTE``).

    Returns:
        A FastAPI dependency that returns the authenticated user on success,
        or raises ``AuthorizationError`` (HTTP 403) on failure.

    Example::

        @router.delete("/targets/{target_id}")
        async def delete_target(
            target_id: uuid.UUID,
            user: Annotated[User, Depends(require_permission(Resource.TARGET, Action.DELETE))],
        ):
            ...
    """

    async def _check(
        current_user: Annotated[Any, Depends(get_current_user)],
    ) -> Any:
        role_names = [r.name for r in current_user.roles]

        if not user_has_permission(role_names, resource, action):
            logger.warning(
                "Permission denied",
                extra={
                    "user_id": str(current_user.id),
                    "resource": resource.value,
                    "action": action.value,
                    "user_roles": role_names,
                },
            )
            raise AuthorizationError(
                f"You do not have permission to {action.value} {resource.value}."
            )

        return current_user

    return _check
