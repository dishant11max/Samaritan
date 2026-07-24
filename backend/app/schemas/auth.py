"""
Authentication request and response schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Credentials submitted to the login endpoint."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    """Payload for new user registration."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """Access + refresh tokens returned after successful login or refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expiry


class RefreshRequest(BaseModel):
    """Payload for the token refresh endpoint."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Payload for logout — revokes the supplied refresh token."""

    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Request a password reset email."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirm password reset using the emailed token."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class EmailVerifyRequest(BaseModel):
    """Confirm email address using the verification token."""

    token: str


class MessageResponse(BaseModel):
    """Generic single-message response (used for password reset, etc.)."""

    message: str
