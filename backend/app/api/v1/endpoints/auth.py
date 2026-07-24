"""Authentication endpoints — register, login, logout, refresh, password reset."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ActiveUserDep, DBDep, get_current_user
from app.schemas.auth import (
    EmailVerifyRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import APIResponse
from app.schemas.user import UserResponse
from app.services import AuthService
from app.utils import success_response
from app.core.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/register", response_model=APIResponse[UserResponse], status_code=201)
@limiter.limit("5/minute")
async def register(request: Request, payload: RegisterRequest, db: DBDep):
    """Register a new user account."""
    svc = AuthService(db)
    user = await svc.register(
        email=payload.email,
        username=payload.username,
        password=payload.password,
        ip_address=_get_client_ip(request),
    )
    return success_response(
        data=UserResponse.model_validate(user),
        message="Account created successfully.",
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/login", response_model=APIResponse[TokenResponse])
@limiter.limit("10/minute")
async def login(payload: LoginRequest, request: Request, db: DBDep):
    """Authenticate and receive access + refresh tokens."""
    svc = AuthService(db)
    tokens = await svc.login(
        email=payload.email,
        password=payload.password,
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    return success_response(
        data=tokens,
        message="Login successful.",
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/refresh", response_model=APIResponse[TokenResponse])
@limiter.limit("20/minute")
async def refresh(payload: RefreshRequest, request: Request, db: DBDep):
    """Rotate refresh token and issue new access token."""
    svc = AuthService(db)
    tokens = await svc.refresh_tokens(
        raw_refresh_token=payload.refresh_token,
        ip_address=_get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    return success_response(data=tokens, request_id=getattr(request.state, "request_id", None))


@router.post("/logout", response_model=APIResponse[None])
@limiter.limit("20/minute")
async def logout(payload: LogoutRequest, request: Request, db: DBDep, current_user: ActiveUserDep):
    """Revoke the supplied refresh token."""
    svc = AuthService(db)
    await svc.logout(
        raw_refresh_token=payload.refresh_token,
        user_id=current_user.id,
        ip_address=_get_client_ip(request),
    )
    return success_response(message="Logged out successfully.", request_id=getattr(request.state, "request_id", None))


@router.post("/password-reset/request", response_model=APIResponse[None])
@limiter.limit("3/minute")
async def request_password_reset(payload: PasswordResetRequest, request: Request, db: DBDep):
    """Request a password reset email (always returns 200 to prevent enumeration)."""
    svc = AuthService(db)
    await svc.request_password_reset(payload.email)
    return success_response(message="If an account exists, a reset link has been sent.")


@router.post("/password-reset/confirm", response_model=APIResponse[None])
@limiter.limit("3/minute")
async def confirm_password_reset(payload: PasswordResetConfirm, request: Request, db: DBDep):
    """Apply a new password using the reset token."""
    svc = AuthService(db)
    await svc.confirm_password_reset(token=payload.token, new_password=payload.new_password)
    return success_response(message="Password updated successfully.")


@router.post("/verify-email", response_model=APIResponse[None])
@limiter.limit("5/minute")
async def verify_email(payload: EmailVerifyRequest, request: Request, db: DBDep):
    """Confirm email address using the verification token."""
    svc = AuthService(db)
    await svc.verify_email(token=payload.token)
    return success_response(message="Email verified successfully.")


@router.get("/me", response_model=APIResponse[UserResponse])
@limiter.limit("60/minute")
async def get_me(current_user: ActiveUserDep, request: Request):
    """Return the currently authenticated user's profile."""
    return success_response(
        data=UserResponse.model_validate(current_user),
        request_id=getattr(request.state, "request_id", None),
    )
