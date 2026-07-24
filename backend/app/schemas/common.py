"""
Common API response schemas used across all endpoints.

Every response from the Samaritan API is wrapped in one of:
  - ``APIResponse[T]``       — single-item success response.
  - ``PaginatedResponse[T]`` — paginated list success response.
  - ``ErrorResponse``        — structured error response.

This ensures a consistent contract for all API consumers.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class APIResponse(BaseModel, Generic[T]):
    """Standard success envelope for single-resource responses."""

    success: bool = True
    message: str = "OK"
    data: T | None = None
    timestamp: str = Field(default_factory=_utcnow_iso)
    request_id: str | None = None

    model_config = {"arbitrary_types_allowed": True}


class PaginationMeta(BaseModel):
    """Pagination metadata included in list responses."""

    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard success envelope for paginated list responses."""

    success: bool = True
    message: str = "OK"
    data: list[T] = Field(default_factory=list)
    meta: PaginationMeta
    timestamp: str = Field(default_factory=_utcnow_iso)
    request_id: str | None = None

    model_config = {"arbitrary_types_allowed": True}


class ErrorDetail(BaseModel):
    """A single structured error detail (used in validation errors)."""

    field: str | None = None
    message: str


class ErrorResponse(BaseModel):
    """Standard error envelope returned for all 4xx and 5xx responses."""

    success: bool = False
    message: str
    error_code: str = "ERROR"
    errors: list[ErrorDetail | str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=_utcnow_iso)
    request_id: str | None = None
