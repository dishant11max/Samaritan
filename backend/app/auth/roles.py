"""
RBAC permission definitions and role-to-permission matrix for Samaritan.

The ``ROLE_PERMISSIONS`` dict is the single source of truth for what
each role is allowed to do.  It is checked at runtime in ``permissions.py``.

Adding a new permission:
  1. Add it to ``ROLE_PERMISSIONS`` for the appropriate roles.
  2. Reference it in route dependencies via ``require_permission()``.

No database lookup is required for permission checks — the matrix is
loaded once at startup, making checks O(1) and zero-latency.
"""

from __future__ import annotations

from app.core.constants import Action, Resource, UserRole

# ---------------------------------------------------------------------------
# Permission tuple type
# ---------------------------------------------------------------------------

# A permission is simply a (resource, action) pair.
Permission = tuple[str, str]


def perm(resource: Resource, action: Action) -> Permission:
    """Construct a permission tuple from Resource and Action enums."""
    return (resource.value, action.value)


# ---------------------------------------------------------------------------
# Role → Permission mapping
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {

    UserRole.ADMIN.value: frozenset(
        {
            # Full user management
            perm(Resource.USER, Action.CREATE),
            perm(Resource.USER, Action.READ),
            perm(Resource.USER, Action.UPDATE),
            perm(Resource.USER, Action.DELETE),
            perm(Resource.USER, Action.LIST),
            # Full role management
            perm(Resource.ROLE, Action.CREATE),
            perm(Resource.ROLE, Action.READ),
            perm(Resource.ROLE, Action.UPDATE),
            perm(Resource.ROLE, Action.DELETE),
            perm(Resource.ROLE, Action.LIST),
            perm(Resource.ROLE, Action.MANAGE),
            # Targets
            perm(Resource.TARGET, Action.CREATE),
            perm(Resource.TARGET, Action.READ),
            perm(Resource.TARGET, Action.UPDATE),
            perm(Resource.TARGET, Action.DELETE),
            perm(Resource.TARGET, Action.LIST),
            # Scans
            perm(Resource.SCAN, Action.CREATE),
            perm(Resource.SCAN, Action.READ),
            perm(Resource.SCAN, Action.UPDATE),
            perm(Resource.SCAN, Action.DELETE),
            perm(Resource.SCAN, Action.LIST),
            perm(Resource.SCAN, Action.EXECUTE),
            # Scan results
            perm(Resource.SCAN_RESULT, Action.READ),
            perm(Resource.SCAN_RESULT, Action.LIST),
            perm(Resource.SCAN_RESULT, Action.UPDATE),
            perm(Resource.SCAN_RESULT, Action.DELETE),
            # Reports
            perm(Resource.REPORT, Action.CREATE),
            perm(Resource.REPORT, Action.READ),
            perm(Resource.REPORT, Action.LIST),
            perm(Resource.REPORT, Action.DELETE),
            perm(Resource.REPORT, Action.EXPORT),
            # Audit logs
            perm(Resource.AUDIT_LOG, Action.READ),
            perm(Resource.AUDIT_LOG, Action.LIST),
            perm(Resource.AUDIT_LOG, Action.EXPORT),
            # System
            perm(Resource.SYSTEM, Action.MANAGE),
        }
    ),

    UserRole.ANALYST.value: frozenset(
        {
            # Own profile only
            perm(Resource.USER, Action.READ),
            # Targets — read all, manage own
            perm(Resource.TARGET, Action.CREATE),
            perm(Resource.TARGET, Action.READ),
            perm(Resource.TARGET, Action.UPDATE),
            perm(Resource.TARGET, Action.LIST),
            # Scans — full scan lifecycle
            perm(Resource.SCAN, Action.CREATE),
            perm(Resource.SCAN, Action.READ),
            perm(Resource.SCAN, Action.UPDATE),
            perm(Resource.SCAN, Action.LIST),
            perm(Resource.SCAN, Action.EXECUTE),
            # Scan results — read and annotate
            perm(Resource.SCAN_RESULT, Action.READ),
            perm(Resource.SCAN_RESULT, Action.LIST),
            perm(Resource.SCAN_RESULT, Action.UPDATE),
            # Reports — generate and export
            perm(Resource.REPORT, Action.CREATE),
            perm(Resource.REPORT, Action.READ),
            perm(Resource.REPORT, Action.LIST),
            perm(Resource.REPORT, Action.EXPORT),
        }
    ),

    UserRole.USER.value: frozenset(
        {
            # Own profile
            perm(Resource.USER, Action.READ),
            perm(Resource.USER, Action.UPDATE),
            # Own targets
            perm(Resource.TARGET, Action.CREATE),
            perm(Resource.TARGET, Action.READ),
            perm(Resource.TARGET, Action.UPDATE),
            perm(Resource.TARGET, Action.DELETE),
            perm(Resource.TARGET, Action.LIST),
            # Own scans
            perm(Resource.SCAN, Action.CREATE),
            perm(Resource.SCAN, Action.READ),
            perm(Resource.SCAN, Action.LIST),
            perm(Resource.SCAN, Action.EXECUTE),
            # Own scan results — read only
            perm(Resource.SCAN_RESULT, Action.READ),
            perm(Resource.SCAN_RESULT, Action.LIST),
            # Own reports
            perm(Resource.REPORT, Action.CREATE),
            perm(Resource.REPORT, Action.READ),
            perm(Resource.REPORT, Action.LIST),
        }
    ),

    UserRole.GUEST.value: frozenset(
        {
            # Read-only access to shared public results
            perm(Resource.SCAN_RESULT, Action.READ),
            perm(Resource.SCAN_RESULT, Action.LIST),
            perm(Resource.REPORT, Action.READ),
        }
    ),
}


def get_role_permissions(role_name: str) -> frozenset[Permission]:
    """
    Return the permission set for a given role name.

    Args:
        role_name: One of the ``UserRole`` enum values.

    Returns:
        A frozenset of ``(resource, action)`` permission tuples.
        Returns an empty frozenset for unknown roles.
    """
    return ROLE_PERMISSIONS.get(role_name, frozenset())


def user_has_permission(
    role_names: list[str],
    resource: Resource,
    action: Action,
) -> bool:
    """
    Check whether a user holding the given roles has a specific permission.

    Args:
        role_names: The role names held by the user.
        resource:   The resource being accessed.
        action:     The action being performed.

    Returns:
        ``True`` if any of the user's roles grants the permission.
    """
    required = perm(resource, action)
    for role_name in role_names:
        if required in get_role_permissions(role_name):
            return True
    return False
