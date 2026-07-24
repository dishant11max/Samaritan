"""
JWT creation and validation utilities for Samaritan.

All token operations are centralised here.  Routes and services must
never decode JWTs directly — they go through ``decode_token()``.

Token design:
  - Access tokens:  short-lived (30 min), signed with SECRET_KEY.
  - Refresh tokens: long-lived (7 days), signed with REFRESH_SECRET_KEY.
  - Separate keys for access and refresh prevent a refresh token from
    being used as an access token (and vice versa).
  - The ``type`` claim enforces this separation at decode time.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.constants import TokenType
from app.core.exceptions import TokenExpiredError, TokenInvalidError


# ---------------------------------------------------------------------------
# Token payload schema
# ---------------------------------------------------------------------------


class TokenPayload(BaseModel):
    """
    Validated claims extracted from a decoded JWT.

    Standard claims:
        sub  — subject (user UUID as string).
        exp  — expiration time (Unix timestamp).
        iat  — issued at (Unix timestamp).
        jti  — JWT ID (unique token identifier).
        type — token type (access | refresh | password_reset | email_verify).

    Custom claims:
        roles — list of role names the subject holds (access tokens only).
    """

    sub: str
    exp: int
    iat: int
    jti: str
    type: TokenType
    roles: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------


def create_access_token(
    subject: str | uuid.UUID,
    roles: list[str] | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject:      User UUID (stored as string in ``sub`` claim).
        roles:        List of role names to embed in the token.
        extra_claims: Additional claims merged into the payload.

    Returns:
        A compact, URL-safe JWT string.
    """
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
        "type": TokenType.ACCESS.value,
        "roles": roles or [],
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    subject: str | uuid.UUID,
    family_id: str | uuid.UUID | None = None,
) -> tuple[str, str]:
    """
    Create a signed JWT refresh token.

    Args:
        subject:   User UUID.
        family_id: Token rotation family ID.  A new UUID is generated if
                   not supplied (first refresh token for this session).

    Returns:
        A tuple of ``(raw_token, family_id_str)`` where ``family_id_str``
        must be stored alongside the token hash in the database.
    """
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    fid = str(family_id) if family_id else str(uuid.uuid4())

    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
        "type": TokenType.REFRESH.value,
        "family_id": fid,
    }

    token = jwt.encode(
        payload, settings.REFRESH_SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return token, fid


def create_email_verify_token(subject: str | uuid.UUID) -> str:
    """Create a short-lived email verification token."""
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(hours=settings.EMAIL_VERIFY_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
        "type": TokenType.EMAIL_VERIFY.value,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_password_reset_token(subject: str | uuid.UUID) -> str:
    """Create a short-lived password reset token."""
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
        "type": TokenType.PASSWORD_RESET.value,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------


def decode_token(
    token: str,
    expected_type: TokenType = TokenType.ACCESS,
) -> TokenPayload:
    """
    Decode and fully validate a JWT.

    Validation checks (in order):
        1. Signature validity.
        2. Expiration (``exp`` claim).
        3. ``type`` claim matches ``expected_type``.
        4. ``sub`` claim present and non-empty.

    Args:
        token:         The raw JWT string from the Authorization header.
        expected_type: The token type this endpoint expects.

    Returns:
        A validated :class:`TokenPayload` instance.

    Raises:
        TokenExpiredError:  The token's ``exp`` is in the past.
        TokenInvalidError:  Signature is invalid, claims are malformed,
                            or the ``type`` claim does not match.
    """
    secret = (
        settings.REFRESH_SECRET_KEY
        if expected_type == TokenType.REFRESH
        else settings.SECRET_KEY
    )

    try:
        raw = jwt.decode(token, secret, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        if "expired" in str(exc).lower():
            raise TokenExpiredError() from exc
        raise TokenInvalidError() from exc

    token_type_value = raw.get("type")
    if token_type_value != expected_type.value:
        raise TokenInvalidError(
            f"Expected token type '{expected_type.value}', "
            f"got '{token_type_value}'."
        )

    if not raw.get("sub"):
        raise TokenInvalidError("Token is missing subject claim.")

    return TokenPayload(**raw)


def hash_token(raw_token: str) -> str:
    """
    Return the SHA-256 hex digest of a raw token string.

    Used to store refresh tokens securely — only the hash is persisted.

    Args:
        raw_token: The plaintext token string.

    Returns:
        64-character lowercase hex string.
    """
    import hashlib
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
