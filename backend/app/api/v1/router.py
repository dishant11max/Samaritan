"""API v1 router — wires all endpoint modules."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.resources import (
    reports_router,
    scans_router,
    targets_router,
)

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(targets_router)
api_router.include_router(scans_router)
api_router.include_router(reports_router)
