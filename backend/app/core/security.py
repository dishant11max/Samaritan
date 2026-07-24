"""
Cryptographic utilities for Samaritan.

Intentionally narrow in scope — this module handles only:
  - Password hashing and verification via bcrypt
  - Password policy enforcement
  - Cryptographically-secure token generation
  - Constant-time string comparison

No JWT operations live here (see ``app/auth/jwt.py``).
No business logic lives here (see ``app/services/auth_service.py``).
"""

from __future__ import annotations

import re
import secrets

from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import WeakPasswordError

# ---------------------------------------------------------------------------
# bcrypt password hashing context
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # NIST-recommended minimum; benchmark <300 ms on target hardware
)


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Args:
        plain_password: The raw password from the user (never stored).

    Returns:
        A bcrypt-hashed string safe to persist in the database.

    Security notes:
        - bcrypt automatically generates a unique salt per call.
        - rounds=12 (~200–400 ms) provides strong resistance to brute force.
        - The plain password is never logged or persisted anywhere.
    """
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against its stored bcrypt hash.

    Uses passlib's constant-time comparison internally to prevent
    timing-based side-channel attacks.

    Args:
        plain_password: Raw password string from the authentication request.
        hashed_password: Stored bcrypt hash retrieved from the database.

    Returns:
        ``True`` if the password matches; ``False`` otherwise.
    """
    return _pwd_context.verify(plain_password, hashed_password)


def validate_password_strength(password: str) -> None:
    """
    Enforce the application password policy defined in ``Settings``.

    Collects *all* policy violations before raising so that the client
    receives a complete list of required changes in a single response.

    Args:
        password: The candidate password string to evaluate.

    Raises:
        WeakPasswordError: If one or more policy constraints are violated.
                           The ``errors`` attribute contains the full list.
    """
    errors: list[str] = []

    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(
            f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long."
        )

    if len(password) > settings.PASSWORD_MAX_LENGTH:
        errors.append(
            f"Password must not exceed {settings.PASSWORD_MAX_LENGTH} characters."
        )

    if settings.PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter (A-Z).")

    if settings.PASSWORD_REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter (a-z).")

    if settings.PASSWORD_REQUIRE_DIGITS and not re.search(r"\d", password):
        errors.append("Password must contain at least one digit (0-9).")

    if settings.PASSWORD_REQUIRE_SPECIAL and not re.search(
        r"[!@#$%^&*()\-_=+\[\]{}|;:'\",.<>?/\\`~]", password
    ):
        errors.append("Password must contain at least one special character.")

    if errors:
        raise WeakPasswordError(errors=errors)


def generate_secure_token(nbytes: int = 32) -> str:
    """
    Generate a cryptographically-secure random URL-safe token.

    Used for password reset tokens, email verification tokens, and
    refresh-token family IDs.

    Args:
        nbytes: Entropy in bytes. Default 32 = 256-bit token.

    Returns:
        A URL-safe base64-encoded string (no padding characters).
    """
    return secrets.token_urlsafe(nbytes)


def safe_str_compare(a: str, b: str) -> bool:
    """
    Compare two strings in constant time to prevent timing attacks.

    Must be used whenever comparing token values or secrets — never use
    ``==`` for security-sensitive string comparisons.

    Args:
        a: First string.
        b: Second string.

    Returns:
        ``True`` if the strings are byte-for-byte equal; ``False`` otherwise.
    """
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
