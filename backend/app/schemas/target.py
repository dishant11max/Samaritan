"""Target request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TargetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    host: str = Field(..., min_length=1, max_length=253)
    description: str | None = Field(None, max_length=1000)
    port_range: str | None = Field(None, max_length=100, examples=["80,443", "1-1024"])
    tags: list[str] | None = None


class TargetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    host: str | None = Field(None, min_length=1, max_length=253)
    description: str | None = None
    port_range: str | None = None
    tags: list[str] | None = None
    is_active: bool | None = None


class TargetResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    host: str
    description: str | None
    port_range: str | None
    tags: list | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
