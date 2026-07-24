"""Scan and ScanResult request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import ScanStatus, ScanType, SeverityLevel


class ScanCreate(BaseModel):
    target_id: uuid.UUID
    scan_type: ScanType
    scan_options: dict[str, Any] | None = None


class ScanResponse(BaseModel):
    id: uuid.UUID
    target_id: uuid.UUID
    created_by: uuid.UUID
    scan_type: ScanType
    status: ScanStatus
    celery_task_id: str | None
    scan_options: dict | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScanResultResponse(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    title: str
    description: str | None
    severity: SeverityLevel
    cvss_score: float | None
    cvss_vector: str | None
    port: int | None
    protocol: str | None
    service: str | None
    evidence: dict | None
    remediation: str | None
    cve_ids: list | None
    false_positive: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScanResultUpdate(BaseModel):
    """Allows analysts to annotate findings."""

    false_positive: bool | None = None
    remediation: str | None = None
    severity: SeverityLevel | None = None
