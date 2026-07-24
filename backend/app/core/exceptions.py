"""
Custom exception hierarchy for Samaritan.

All application exceptions extend ``SamaritanException``, which carries
an HTTP status code, a safe user-facing message, a machine-readable error
code, and an optional structured error list for validation feedback.

The global exception handler in ``main.py`` catches every
``SamaritanException`` and converts it to the standard ``ErrorResponse``
format — ensuring no stack traces or internal details leak to clients.

Usage::

    from app.core.exceptions import NotFoundError
    raise NotFoundError("Scan not found.")
"""

from __future__ import annotations

from typing import Any


class SamaritanException(Exception):
    """
    Base exception for all Samaritan application errors.

    Attributes:
        status_code: HTTP status code returned to the client.
        message: Safe, user-facing error description.
        error_code: Machine-readable identifier (e.g. ``"TOKEN_EXPIRED"``).
        errors: Optional list of structured error details.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        errors: list[Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.errors: list[Any] = errors or []


# ---------------------------------------------------------------------------
# 400 Bad Request
# ---------------------------------------------------------------------------


class BadRequestError(SamaritanException):
    """Raised when the client sends a malformed or logically invalid request."""

    def __init__(
        self,
        message: str = "Bad request.",
        errors: list[Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=400,
            error_code="BAD_REQUEST",
            errors=errors,
        )


class WeakPasswordError(SamaritanException):
    """Raised when a password does not satisfy the configured security policy."""

    def __init__(self, errors: list[str] | None = None) -> None:
        super().__init__(
            message="Password does not meet the security policy requirements.",
            status_code=400,
            error_code="WEAK_PASSWORD",
            errors=errors or [],
        )


# ---------------------------------------------------------------------------
# 401 Unauthorized
# ---------------------------------------------------------------------------


class AuthenticationError(SamaritanException):
    """Raised when authentication credentials are absent or invalid."""

    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_REQUIRED",
        )


class InvalidCredentialsError(SamaritanException):
    """Raised when email/password combination is incorrect during login."""

    def __init__(self) -> None:
        super().__init__(
            # Deliberately vague to prevent username enumeration.
            message="Invalid email or password.",
            status_code=401,
            error_code="INVALID_CREDENTIALS",
        )


class TokenExpiredError(SamaritanException):
    """Raised when a JWT or token has passed its expiration time."""

    def __init__(self, message: str = "Token has expired.") -> None:
        super().__init__(
            message=message,
            status_code=401,
            error_code="TOKEN_EXPIRED",
        )


class TokenInvalidError(SamaritanException):
    """Raised when a JWT signature, format, or claims are invalid."""

    def __init__(self, message: str = "Token is invalid.") -> None:
        super().__init__(
            message=message,
            status_code=401,
            error_code="TOKEN_INVALID",
        )


class TokenRevokedError(SamaritanException):
    """Raised when a refresh token has been explicitly revoked."""

    def __init__(self) -> None:
        super().__init__(
            message="Token has been revoked.",
            status_code=401,
            error_code="TOKEN_REVOKED",
        )


# ---------------------------------------------------------------------------
# 403 Forbidden
# ---------------------------------------------------------------------------


class AuthorizationError(SamaritanException):
    """Raised when an authenticated user lacks permission for the action."""

    def __init__(
        self, message: str = "You do not have permission to perform this action."
    ) -> None:
        super().__init__(
            message=message,
            status_code=403,
            error_code="FORBIDDEN",
        )


class OwnershipError(SamaritanException):
    """Raised when a user attempts to access a resource they do not own."""

    def __init__(self) -> None:
        super().__init__(
            message="You do not have access to this resource.",
            status_code=403,
            error_code="OWNERSHIP_REQUIRED",
        )


# ---------------------------------------------------------------------------
# 404 Not Found
# ---------------------------------------------------------------------------


class NotFoundError(SamaritanException):
    """Raised when a requested resource does not exist or has been soft-deleted."""

    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND",
        )


# ---------------------------------------------------------------------------
# 409 Conflict
# ---------------------------------------------------------------------------


class ConflictError(SamaritanException):
    """Raised when a request conflicts with existing state (e.g. duplicate email)."""

    def __init__(self, message: str = "Resource already exists.") -> None:
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT",
        )


# ---------------------------------------------------------------------------
# 422 Unprocessable Entity
# ---------------------------------------------------------------------------


class ValidationError(SamaritanException):
    """Raised when business-level validation fails beyond Pydantic's schema checks."""

    def __init__(
        self,
        message: str = "Validation failed.",
        errors: list[Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=422,
            error_code="VALIDATION_ERROR",
            errors=errors,
        )


# ---------------------------------------------------------------------------
# 423 Locked
# ---------------------------------------------------------------------------


class AccountLockedError(SamaritanException):
    """Raised when a user account is temporarily locked due to failed login attempts."""

    def __init__(self, message: str = "Account is temporarily locked.") -> None:
        super().__init__(
            message=message,
            status_code=423,
            error_code="ACCOUNT_LOCKED",
        )


# ---------------------------------------------------------------------------
# 429 Too Many Requests
# ---------------------------------------------------------------------------


class RateLimitError(SamaritanException):
    """Raised when a client exceeds the configured request rate limit."""

    def __init__(
        self, message: str = "Too many requests. Please try again later."
    ) -> None:
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
        )


# ---------------------------------------------------------------------------
# 500 Internal Server Error
# ---------------------------------------------------------------------------


class InternalError(SamaritanException):
    """
    Raised for unexpected server-side failures.

    The ``message`` defaults to a generic string intentionally — specific
    details are written to the server log but never returned to the client.
    """

    def __init__(
        self, message: str = "An unexpected error occurred. Please try again later."
    ) -> None:
        super().__init__(
            message=message,
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        )


class DatabaseError(SamaritanException):
    """Raised when a database operation fails unexpectedly."""

    def __init__(self) -> None:
        super().__init__(
            message="A database error occurred. Please try again later.",
            status_code=500,
            error_code="DATABASE_ERROR",
        )
