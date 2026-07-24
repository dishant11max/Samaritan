"""
Samaritan FastAPI application entrypoint.

Startup sequence:
  1. Configure structured logging.
  2. Verify PostgreSQL connectivity.
  3. Verify Redis connectivity.
  4. Seed default roles and admin user (idempotent).
  5. Register all middleware (order matters — outermost registered last).
  6. Mount the API router.
  7. Register global exception handlers.
"""

from __future__ import annotations

import traceback
import uuid
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
import app.db.models  # noqa: F401 — register models before API starts
from app.core.exceptions import SamaritanException
from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionLocal, async_engine, redis_pool
from app.middleware import (
    CorrelationIdMiddleware,
    RequestLoggerMiddleware,
    SecurityHeadersMiddleware,
)
from app.schemas.common import ErrorDetail, ErrorResponse
from app.utils import utcnow

configure_logging()
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown event handler."""

    # ---- Startup ----
    logger.info("Starting Samaritan backend", extra={"version": settings.VERSION})

    # Verify PostgreSQL
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL connection verified.")
    except Exception as exc:
        logger.error("PostgreSQL connection failed", exc_info=exc)

    # Verify Redis
    try:
        _redis = aioredis.Redis(connection_pool=redis_pool)
        await _redis.ping()
        await _redis.aclose()
        logger.info("Redis connection verified.")
    except Exception as exc:
        logger.warning("Redis connection failed — caching unavailable", exc_info=exc)

    # Seed default data
    try:
        from app.db.init_db import init_db
        async with AsyncSessionLocal() as session:
            await init_db(session)
    except Exception as exc:
        logger.error("Database initialisation failed", exc_info=exc)

    yield

    # ---- Shutdown ----
    logger.info("Shutting down Samaritan backend.")
    await async_engine.dispose()
    await redis_pool.aclose()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Samaritan — Production-grade cybersecurity vulnerability scanning platform. "
        "Manage targets, execute scans, analyse findings, and generate reports."
    ),
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
    # Never expose stack traces in production
    debug=settings.DEBUG,
)

# ---------------------------------------------------------------------------
# Middleware (registered in reverse execution order)
# ---------------------------------------------------------------------------

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggerMiddleware)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.TRUSTED_HOSTS + ["*"]
    if settings.ENVIRONMENT == "development"
    else settings.TRUSTED_HOSTS,
)

# ---------------------------------------------------------------------------
# API Router
# ---------------------------------------------------------------------------

app.include_router(api_router, prefix=settings.API_V1_STR)


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def root():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
        "status": "running",
    }


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------


def _make_error_response(
    message: str,
    error_code: str,
    errors: list[Any] | None,
    request: Request,
    status_code: int,
):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ErrorResponse(
        message=message,
        error_code=error_code,
        errors=errors or [],
        request_id=request_id,
    )


@app.exception_handler(SamaritanException)
async def samaritan_exception_handler(request: Request, exc: SamaritanException):
    from fastapi.responses import JSONResponse
    logger.warning(
        "Application exception",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "path": request.url.path,
        },
    )
    body = _make_error_response(
        message=exc.message,
        error_code=exc.error_code,
        errors=exc.errors,
        request=request,
        status_code=exc.status_code,
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    from fastapi.responses import JSONResponse
    errors = [
        ErrorDetail(
            field=".".join(str(loc) for loc in e.get("loc", [])),
            message=e.get("msg", "Validation error"),
        )
        for e in exc.errors()
    ]
    body = _make_error_response(
        message="Request validation failed.",
        error_code="VALIDATION_ERROR",
        errors=errors,
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=body.model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    from fastapi.responses import JSONResponse
    logger.error(
        "Unhandled exception",
        extra={"path": request.url.path},
        exc_info=exc,
    )
    body = _make_error_response(
        message="An unexpected error occurred. Please try again later.",
        error_code="INTERNAL_SERVER_ERROR",
        errors=[],
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=body.model_dump(),
    )
