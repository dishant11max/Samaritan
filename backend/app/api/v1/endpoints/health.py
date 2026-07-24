"""Health check endpoint."""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_redis

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", summary="Health check")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Return service health status for PostgreSQL and Redis."""
    db_ok, redis_ok = False, False

    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    try:
        await redis.ping()
        redis_ok = True
    except Exception:
        pass

    status = "healthy" if (db_ok and redis_ok) else "degraded"
    return {
        "status": status,
        "services": {"database": "ok" if db_ok else "error", "redis": "ok" if redis_ok else "error"},
    }
