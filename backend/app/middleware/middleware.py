"""
Security headers, correlation ID, and request logging middleware.
"""

from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.constants import SecurityHeader
from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Correlation ID Middleware
# ---------------------------------------------------------------------------

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Injects a unique ``X-Request-ID`` header on every request and response.

    If the client sends an ``X-Request-ID`` header, it is echoed back;
    otherwise a new UUID4 is generated.  The ID is stored in request state
    so other middleware and route handlers can access it.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get(
            SecurityHeader.X_REQUEST_ID, str(uuid.uuid4())
        )
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[SecurityHeader.X_REQUEST_ID] = request_id
        return response


# ---------------------------------------------------------------------------
# Request Logger Middleware
# ---------------------------------------------------------------------------

class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """
    Logs every incoming request and its response time.

    Sensitive paths (login, password reset) omit the request body from logs.
    """

    _SENSITIVE_PATHS = frozenset({"/auth/login", "/auth/register", "/auth/reset-password"})

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        request_id = getattr(request.state, "request_id", "-")

        logger.info(
            "Incoming request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "request_id": request_id,
                "client_ip": request.client.host if request.client else "unknown",
            },
        )

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers[SecurityHeader.X_RESPONSE_TIME] = f"{duration_ms}ms"

        logger.info(
            "Response sent",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "request_id": request_id,
            },
        )
        return response


# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds production-grade HTTP security headers to every response.

    Headers applied:
      - Strict-Transport-Security (HSTS)
      - X-Content-Type-Options: nosniff
      - X-Frame-Options: DENY
      - Referrer-Policy: strict-origin-when-cross-origin
      - Cache-Control: no-store (for API responses)
      - Permissions-Policy: restrictive default
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers[SecurityHeader.X_CONTENT_TYPE_OPTIONS] = "nosniff"
        response.headers[SecurityHeader.X_FRAME_OPTIONS] = "DENY"
        response.headers[SecurityHeader.X_XSS_PROTECTION] = "1; mode=block"
        response.headers[SecurityHeader.REFERRER_POLICY] = "strict-origin-when-cross-origin"
        response.headers[SecurityHeader.CACHE_CONTROL] = "no-store"
        response.headers[SecurityHeader.PERMISSIONS_POLICY] = (
            "geolocation=(), microphone=(), camera=()"
        )
        response.headers[SecurityHeader.STRICT_TRANSPORT_SECURITY] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        return response
