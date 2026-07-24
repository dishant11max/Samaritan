"""
Authentication service — business logic for all auth flows.

Responsibilities:
  - User registration with duplicate detection and password policy.
  - Login with brute-force protection and account lockout.
  - Access + refresh token issuance and rotation.
  - Logout (refresh token revocation).
  - Password reset flow (token generation → verification → update).
  - Email verification token issuance.

No HTTP details (headers, cookies, request objects) belong here.
No SQL belongs here — all DB access goes through repositories.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import (
    create_access_token,
    create_email_verify_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_token,
)
from app.core.config import settings
from app.core.constants import AuditEventType, AuditStatus, TokenType
from app.core.exceptions import (
    AccountLockedError,
    ConflictError,
    InvalidCredentialsError,
    NotFoundError,
    TokenInvalidError,
    TokenRevokedError,
)
from app.core.logging import get_logger
from app.core.security import hash_password, validate_password_strength, verify_password
from app.repositories import (
    AuditLogRepository,
    RefreshTokenRepository,
    RoleRepository,
    UserRepository,
)
from app.schemas.auth import TokenResponse

logger = get_logger(__name__)


class AuthService:
    """Stateless authentication service — instantiated per request."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._roles = RoleRepository(session)
        self._tokens = RefreshTokenRepository(session)
        self._audit = AuditLogRepository(session)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(
        self,
        email: str,
        username: str,
        password: str,
        ip_address: str | None = None,
    ) -> "User":  # noqa: F821
        """
        Register a new user account.

        Raises:
            ConflictError:  Email or username already taken.
            WeakPasswordError: Password fails policy.
        """
        validate_password_strength(password)

        if await self._users.email_exists(email.lower().strip()):
            raise ConflictError("An account with this email address already exists.")

        if await self._users.username_exists(username.strip()):
            raise ConflictError("This username is already taken.")

        default_role = await self._roles.get_by_name("user")

        user = await self._users.create(
            id=uuid.uuid4(),
            email=email.lower().strip(),
            username=username.strip(),
            hashed_password=hash_password(password),
            is_active=True,
            is_verified=False,
            is_superuser=False,
        )

        if default_role:
            user.roles.append(default_role)
            self._session.add(user)
            await self._session.flush()

        await self._audit.log(
            event_type=AuditEventType.USER_REGISTERED,
            user_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
            ip_address=ip_address,
        )

        logger.info("User registered", extra={"user_id": str(user.id)})
        return user

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    async def login(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """
        Authenticate a user and return an access + refresh token pair.

        Implements brute-force protection:
          - After ``MAX_LOGIN_ATTEMPTS`` failures, account is locked for
            ``LOCKOUT_DURATION_MINUTES`` minutes.
          - Lockout is checked before password verification to prevent
            timing-based information leakage.

        Raises:
            AccountLockedError:     Account is temporarily locked.
            InvalidCredentialsError: Email/password is wrong.
        """
        user = await self._users.get_by_email(email.lower().strip())

        if user is None:
            # Always perform a dummy hash to prevent user enumeration
            # via timing differences.
            verify_password("dummy", "$2b$12$dummy_hash_to_prevent_timing_attacks______")
            raise InvalidCredentialsError()

        # Check lockout before password verification.
        if user.locked_until and user.locked_until > datetime.now(tz=timezone.utc):
            await self._audit.log(
                event_type=AuditEventType.USER_LOGIN_FAILED,
                status=AuditStatus.FAILURE,
                user_id=user.id,
                ip_address=ip_address,
            )
            raise AccountLockedError()

        if not verify_password(password, user.hashed_password):
            user = await self._users.increment_failed_attempts(user)

            if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                locked_until = datetime.now(tz=timezone.utc) + timedelta(
                    minutes=settings.LOCKOUT_DURATION_MINUTES
                )
                await self._users.update(user, locked_until=locked_until)
                await self._audit.log(
                    event_type=AuditEventType.USER_LOCKED,
                    user_id=user.id,
                    ip_address=ip_address,
                )
                logger.warning(
                    "Account locked after failed attempts",
                    extra={"user_id": str(user.id)},
                )

            await self._audit.log(
                event_type=AuditEventType.USER_LOGIN_FAILED,
                status=AuditStatus.FAILURE,
                user_id=user.id,
                ip_address=ip_address,
            )
            raise InvalidCredentialsError()

        # Successful login — reset counters.
        await self._users.reset_failed_attempts(user)
        await self._users.update(user, last_login_at=datetime.now(tz=timezone.utc))

        role_names = [r.name for r in user.roles]
        access_token = create_access_token(subject=user.id, roles=role_names)
        raw_refresh, family_id = create_refresh_token(subject=user.id)

        await self._tokens.create(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            family_id=uuid.UUID(family_id),
            expires_at=datetime.now(tz=timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._audit.log(
            event_type=AuditEventType.USER_LOGIN,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info("User logged in", extra={"user_id": str(user.id)})

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ------------------------------------------------------------------
    # Token Refresh
    # ------------------------------------------------------------------

    async def refresh_tokens(
        self,
        raw_refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """
        Rotate a refresh token — revoke old, issue new access + refresh pair.

        Replay protection: if the presented token is already revoked,
        revoke the entire token family (session hijack response).
        """
        payload = decode_token(raw_refresh_token, expected_type=TokenType.REFRESH)
        token_hash = hash_token(raw_refresh_token)
        stored = await self._tokens.get_by_hash(token_hash)

        if stored is None:
            raise TokenInvalidError("Refresh token not found.")

        if stored.is_revoked:
            # Potential replay attack — revoke the whole family.
            await self._tokens.revoke_family(stored.family_id)
            logger.warning(
                "Revoked refresh token replayed — family revoked",
                extra={"family_id": str(stored.family_id)},
            )
            raise TokenRevokedError()

        if stored.is_expired:
            raise TokenInvalidError("Refresh token has expired.")

        # Revoke the old token.
        await self._tokens.revoke_token(stored)

        user = await self._users.get_by_id(stored.user_id)
        if user is None or not user.is_active:
            raise InvalidCredentialsError()

        role_names = [r.name for r in user.roles]
        access_token = create_access_token(subject=user.id, roles=role_names)
        raw_new_refresh, _ = create_refresh_token(
            subject=user.id, family_id=stored.family_id
        )

        await self._tokens.create(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=hash_token(raw_new_refresh),
            family_id=stored.family_id,
            expires_at=datetime.now(tz=timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._audit.log(
            event_type=AuditEventType.TOKEN_REFRESHED,
            user_id=user.id,
            ip_address=ip_address,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_new_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    async def logout(
        self,
        raw_refresh_token: str,
        user_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> None:
        """Revoke a single refresh token (single-device logout)."""
        token_hash = hash_token(raw_refresh_token)
        stored = await self._tokens.get_by_hash(token_hash)

        if stored and stored.user_id == user_id:
            await self._tokens.revoke_token(stored)

        await self._audit.log(
            event_type=AuditEventType.USER_LOGOUT,
            user_id=user_id,
            ip_address=ip_address,
        )

    async def logout_all(self, user_id: uuid.UUID) -> None:
        """Revoke every refresh token for a user (logout everywhere)."""
        await self._tokens.revoke_all_for_user(user_id)

    # ------------------------------------------------------------------
    # Password Reset
    # ------------------------------------------------------------------

    async def request_password_reset(self, email: str) -> str | None:
        """
        Generate a password reset token for the user with the given email.

        Returns the raw token (to be emailed) or None if the email is not
        found — the caller should always return a success response to
        prevent email enumeration.
        """
        user = await self._users.get_by_email(email.lower().strip())
        if user is None:
            return None

        token = create_password_reset_token(subject=user.id)

        await self._audit.log(
            event_type=AuditEventType.PASSWORD_RESET_REQUESTED,
            user_id=user.id,
        )
        return token

    async def confirm_password_reset(self, token: str, new_password: str) -> None:
        """Apply a new password after verifying the reset token."""
        validate_password_strength(new_password)
        payload = decode_token(token, expected_type=TokenType.PASSWORD_RESET)

        user = await self._users.get_by_id(uuid.UUID(payload.sub))
        if user is None:
            raise NotFoundError("User not found.")

        await self._users.update(user, hashed_password=hash_password(new_password))
        await self._audit.log(
            event_type=AuditEventType.PASSWORD_RESET_COMPLETED,
            user_id=user.id,
        )

    # ------------------------------------------------------------------
    # Email Verification
    # ------------------------------------------------------------------

    async def send_email_verification(self, user_id: uuid.UUID) -> str:
        """Generate an email verification token."""
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return create_email_verify_token(subject=user.id)

    async def verify_email(self, token: str) -> None:
        """Mark a user's email as verified."""
        payload = decode_token(token, expected_type=TokenType.EMAIL_VERIFY)
        user = await self._users.get_by_id(uuid.UUID(payload.sub))
        if user is None:
            raise NotFoundError("User not found.")
        await self._users.update(user, is_verified=True)
        await self._audit.log(
            event_type=AuditEventType.EMAIL_VERIFIED, user_id=user.id
        )


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.db.models.user import User
