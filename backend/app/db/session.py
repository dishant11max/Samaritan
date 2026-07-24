"""
Database engine and session factories for Samaritan.

Provides:
  - ``engine``          — synchronous engine (Alembic migrations, health checks).
  - ``async_engine``    — asynchronous engine (application runtime).
  - ``AsyncSessionLocal`` — async session factory for request-scoped sessions.
  - ``redis_pool``      — shared async Redis connection pool.

Architecture note:
    The async engine uses the same ``postgresql+psycopg`` dialect as the sync
    engine. psycopg3 supports both sync and async via the same URL scheme when
    paired with SQLAlchemy's ``create_async_engine``. This avoids installing a
    second driver (e.g. asyncpg).

Pool configuration:
    ``pool_pre_ping=True`` — validates connections before handing them to the
    application, recovering silently from idle connection drops.
    ``pool_size`` and ``max_overflow`` are tuned for moderate concurrency.
    These should be adjusted via environment variables for production workloads.
"""

from __future__ import annotations

import redis.asyncio as aioredis
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# ---------------------------------------------------------------------------
# Synchronous engine — used ONLY by Alembic and startup health checks.
# Application code must never import this for request handling.
# ---------------------------------------------------------------------------

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SyncSessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# ---------------------------------------------------------------------------
# Asynchronous engine — the primary database interface for the application.
# ---------------------------------------------------------------------------

async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    # Recycle connections older than 30 minutes to avoid stale state.
    pool_recycle=1800,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevents lazy-load errors after commit in async context.
    autocommit=False,
    autoflush=False,
)

# ---------------------------------------------------------------------------
# Redis connection pool — shared across all async Redis dependencies.
# Initialised here; pool lifecycle is managed by the app lifespan in main.py.
# ---------------------------------------------------------------------------

redis_pool: aioredis.ConnectionPool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=20,
    decode_responses=True,
)
