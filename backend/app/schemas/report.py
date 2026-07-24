"""Report request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import ReportFormat


class ReportCreate(BaseModel):
    scan_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=255)
    summary: str | None = None
    format: ReportFormat = ReportFormat.JSON
    is_public: bool = False


class ReportResponse(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    generated_by: uuid.UUID
    title: str
    summary: str | None
    format: ReportFormat
    file_path: str | None
    is_public: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
