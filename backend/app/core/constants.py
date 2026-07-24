"""
Application-wide constants and enumerations.

All enumerations used across models, schemas, services, and business logic
are centralised here to eliminate duplication and provide a single source of
truth. Using ``str, Enum`` mixins ensures values are JSON-serialisable and
compatible with SQLAlchemy's native Enum columns.
"""

from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# User & Authentication
# ---------------------------------------------------------------------------


class UserRole(str, Enum):
    """Hierarchical roles assigned to users for RBAC enforcement."""

    ADMIN = "admin"
    ANALYST = "analyst"
    USER = "user"
    GUEST = "guest"


class TokenType(str, Enum):
    """Distinguishes the purpose of a signed JWT or opaque token."""

    ACCESS = "access"
    REFRESH = "refresh"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFY = "email_verify"


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


class ScanStatus(str, Enum):
    """Lifecycle state of a vulnerability scan, mirroring Celery task states."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanType(str, Enum):
    """Category of scan to be executed by the scan engine."""

    PORT_SCAN = "port_scan"
    VULNERABILITY_SCAN = "vulnerability_scan"
    WEB_SCAN = "web_scan"
    NETWORK_SCAN = "network_scan"


class SeverityLevel(str, Enum):
    """
    CVSS v3-aligned severity classification for scan findings.

    Maps to CVSS base score ranges:
        CRITICAL       9.0 – 10.0
        HIGH           7.0 – 8.9
        MEDIUM         4.0 – 6.9
        LOW            0.1 – 3.9
        INFORMATIONAL  0.0
        NONE           (no score assigned)
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"
    NONE = "none"


class ReportFormat(str, Enum):
    """Supported output formats for generated vulnerability reports."""

    PDF = "pdf"
    JSON = "json"
    HTML = "html"
    CSV = "csv"


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------


class AuditEventType(str, Enum):
    """All auditable events tracked in the immutable audit log."""

    # Authentication
    USER_REGISTERED = "user_registered"
    USER_LOGIN = "user_login"
    USER_LOGIN_FAILED = "user_login_failed"
    USER_LOGOUT = "user_logout"
    USER_LOCKED = "user_locked"
    USER_UNLOCKED = "user_unlocked"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"

    # Password & Email
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    EMAIL_VERIFIED = "email_verified"

    # Tokens
    TOKEN_REFRESHED = "token_refreshed"
    TOKEN_REVOKED = "token_revoked"

    # Scanning
    SCAN_CREATED = "scan_created"
    SCAN_STARTED = "scan_started"
    SCAN_COMPLETED = "scan_completed"
    SCAN_FAILED = "scan_failed"
    SCAN_CANCELLED = "scan_cancelled"

    # Targets
    TARGET_CREATED = "target_created"
    TARGET_UPDATED = "target_updated"
    TARGET_DELETED = "target_deleted"

    # Reports
    REPORT_GENERATED = "report_generated"

    # Access Control
    PERMISSION_DENIED = "permission_denied"


class AuditStatus(str, Enum):
    """Outcome of an audited event."""

    SUCCESS = "success"
    FAILURE = "failure"


# ---------------------------------------------------------------------------
# RBAC Resources & Actions
# ---------------------------------------------------------------------------


class Resource(str, Enum):
    """Protected resources in the RBAC permission matrix."""

    USER = "user"
    ROLE = "role"
    TARGET = "target"
    SCAN = "scan"
    SCAN_RESULT = "scan_result"
    REPORT = "report"
    AUDIT_LOG = "audit_log"
    SYSTEM = "system"


class Action(str, Enum):
    """Permitted actions that can be granted on a Resource."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    EXECUTE = "execute"
    EXPORT = "export"
    MANAGE = "manage"


# ---------------------------------------------------------------------------
# HTTP Security Headers
# ---------------------------------------------------------------------------


class SecurityHeader:
    """Standard HTTP response security header names."""

    STRICT_TRANSPORT_SECURITY: str = "Strict-Transport-Security"
    CONTENT_SECURITY_POLICY: str = "Content-Security-Policy"
    X_CONTENT_TYPE_OPTIONS: str = "X-Content-Type-Options"
    X_FRAME_OPTIONS: str = "X-Frame-Options"
    X_XSS_PROTECTION: str = "X-XSS-Protection"
    REFERRER_POLICY: str = "Referrer-Policy"
    PERMISSIONS_POLICY: str = "Permissions-Policy"
    CACHE_CONTROL: str = "Cache-Control"
    X_REQUEST_ID: str = "X-Request-ID"
    X_CORRELATION_ID: str = "X-Correlation-ID"
    X_RESPONSE_TIME: str = "X-Response-Time"


# ---------------------------------------------------------------------------
# Pagination defaults
# ---------------------------------------------------------------------------

DEFAULT_PAGE: int = 1
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100
