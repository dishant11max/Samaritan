"""
Structured logging configuration for Samaritan.

Provides:
  - JSON formatter for production / staging (compatible with log aggregators
    such as Loki, CloudWatch, Datadog, and Elastic).
  - Human-readable console formatter for local development.
  - A ``_RedactingFilter`` that scrubs known sensitive field names from every
    log record — passwords, tokens, and secrets are never written to logs.
  - A ``get_logger(name)`` factory used throughout the codebase.
  - A ``configure_logging()`` function called once at startup.

Usage::

    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("User registered", extra={"user_id": str(user.id)})
"""

from __future__ import annotations

import json
import logging
import logging.config
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

# ---------------------------------------------------------------------------
# Sensitive field redaction
# ---------------------------------------------------------------------------

_REDACTED_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "hashed_password",
        "plain_password",
        "new_password",
        "old_password",
        "confirm_password",
        "token",
        "access_token",
        "refresh_token",
        "reset_token",
        "verify_token",
        "secret",
        "secret_key",
        "api_key",
        "authorization",
        "cookie",
        "smtp_password",
    }
)


class _RedactingFilter(logging.Filter):
    """
    Logging filter that replaces sensitive attribute values with ``[REDACTED]``.

    Operates on LogRecord extras added via ``extra={"key": "value"}`` in
    logger calls. Does NOT examine the message string itself — format your
    log messages to never include raw secrets.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        for key in list(vars(record).keys()):
            if key.lower() in _REDACTED_KEYS:
                setattr(record, key, "[REDACTED]")
        return True


# ---------------------------------------------------------------------------
# JSON formatter (production / staging)
# ---------------------------------------------------------------------------


class _JSONFormatter(logging.Formatter):
    """
    Formats each log record as a single-line JSON object.

    Designed for log aggregation pipelines that parse JSON log streams
    (e.g. Loki, Elastic, CloudWatch Logs Insights).
    """

    # Fields that belong to the internal LogRecord structure, not to the
    # application-level extra payload.
    _SKIP_KEYS: frozenset[str] = frozenset(
        {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Attach application-level extras.
        for key, value in vars(record).items():
            if key not in self._SKIP_KEYS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# Logging configuration dict
# ---------------------------------------------------------------------------

def _build_logging_config() -> dict[str, Any]:
    is_development = settings.ENVIRONMENT == "development"
    log_level = "DEBUG" if settings.DEBUG else "INFO"

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "redacting": {
                "()": _RedactingFilter,
            }
        },
        "formatters": {
            "json": {
                "()": _JSONFormatter,
            },
            "console": {
                "format": (
                    "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
                ),
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "console" if is_development else "json",
                "filters": ["redacting"],
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console"],
        },
        "loggers": {
            # Reduce noise from third-party libraries in production.
            "uvicorn": {"level": "INFO", "propagate": True},
            "uvicorn.access": {"level": "WARNING", "propagate": False},
            "sqlalchemy.engine": {
                "level": "DEBUG" if settings.DEBUG else "WARNING",
                "propagate": True,
            },
            "alembic": {"level": "INFO", "propagate": True},
            "celery": {"level": "INFO", "propagate": True},
            "httpx": {"level": "WARNING", "propagate": True},
        },
    }


def configure_logging() -> None:
    """
    Apply the logging configuration.

    Must be called once at application startup (inside the lifespan handler
    in ``main.py``). Calling it multiple times is safe — ``dictConfig`` is
    idempotent when ``disable_existing_loggers=False``.
    """
    logging.config.dictConfig(_build_logging_config())


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger with Samaritan's configuration applied.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A configured :class:`logging.Logger` instance.

    Example::

        logger = get_logger(__name__)
        logger.info("Scan completed", extra={"scan_id": str(scan_id), "duration_ms": 1234})
    """
    return logging.getLogger(name)
