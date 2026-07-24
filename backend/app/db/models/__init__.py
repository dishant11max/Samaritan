"""
``app.db.models`` — ORM model registry.

All models are imported here so that:
  1. SQLAlchemy's mapper is fully configured before the application starts.
  2. Alembic's ``autogenerate`` sees every table when it inspects
     ``Base.metadata``.

Import order matters: association tables must be registered before the
models that reference them as ``secondary`` targets.
"""

from app.db.models.associations import role_permissions, user_roles
from app.db.models.audit_log import AuditLog
from app.db.models.refresh_token import RefreshToken
from app.db.models.report import Report
from app.db.models.role import Permission, Role
from app.db.models.scan import Scan
from app.db.models.scan_result import ScanResult
from app.db.models.target import Target
from app.db.models.user import User

__all__ = [
    # Association tables (must come first)
    "user_roles",
    "role_permissions",
    # Models
    "User",
    "Role",
    "Permission",
    "RefreshToken",
    "Target",
    "Scan",
    "ScanResult",
    "Report",
    "AuditLog",
]
