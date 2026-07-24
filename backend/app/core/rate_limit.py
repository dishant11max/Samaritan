"""
Rate limiting configuration using SlowAPI and Redis.
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

def get_client_ip(request: Request) -> str:
    """Extract the real client IP address for rate limiting."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

_redis_url = settings.REDIS_URL

try:
    limiter = Limiter(
        key_func=get_client_ip,
        storage_uri=_redis_url,
        strategy="fixed-window",
    )
except Exception as exc:
    logger.error("Failed to initialize Redis rate limiter. Falling back to memory.", exc_info=exc)
    limiter = Limiter(key_func=get_client_ip)
