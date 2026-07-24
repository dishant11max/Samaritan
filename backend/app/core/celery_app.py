"""
Celery background task orchestrator.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

# Initialize Celery app
# Using redis for both broker and result backend.
celery_app = Celery(
    "samaritan",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.worker.tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # Max 1 hour per task
)
