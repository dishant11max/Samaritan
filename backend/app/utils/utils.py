"""Utility helpers, response factories, and pagination."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any, TypeVar

from fastapi import Query
from pydantic import BaseModel

from app.schemas.common import (
    APIResponse,
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
    PaginationMeta,
)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class PaginationParams(BaseModel):
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def paginate(
    items: list[Any],
    total: int,
    page: int,
    page_size: int,
    *,
    message: str = "OK",
    request_id: str | None = None,
) -> PaginatedResponse:
    total_pages = math.ceil(total / page_size) if page_size > 0 else 0
    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        ),
        message=message,
        request_id=request_id,
    )


# ---------------------------------------------------------------------------
# Response factories
# ---------------------------------------------------------------------------


def success_response(
    data: Any = None,
    message: str = "OK",
    request_id: str | None = None,
) -> APIResponse:
    return APIResponse(data=data, message=message, request_id=request_id)


def error_response(
    message: str,
    error_code: str = "ERROR",
    errors: list[Any] | None = None,
    request_id: str | None = None,
) -> ErrorResponse:
    return ErrorResponse(
        message=message,
        error_code=error_code,
        errors=errors or [],
        request_id=request_id,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(tz=timezone.utc)


def generate_request_id() -> str:
    """Generate a unique request correlation ID."""
    return str(uuid.uuid4())
