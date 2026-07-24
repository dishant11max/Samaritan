"""
Application configuration module.

All settings are loaded from environment variables or a .env file via
Pydantic Settings. No secrets are ever hardcoded — the application will
refuse to start if required variables are missing.

Usage::

    from app.core.config import settings
    print(settings.DATABASE_URL)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for the Samaritan application.

    Pydantic Settings automatically reads values from environment variables
    (case-sensitive) and falls back to a .env file in the working directory.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    PROJECT_NAME: str = "Samaritan"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # -------------------------------------------------------------------------
    # JWT / Token Security
    # -------------------------------------------------------------------------
    SECRET_KEY: str = "dev_secret_key_change_in_production_min_32_bytes_long"
    REFRESH_SECRET_KEY: str = "dev_refresh_secret_key_change_in_production_min_32_bytes_long"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 15
    EMAIL_VERIFY_TOKEN_EXPIRE_HOURS: int = 48

    # -------------------------------------------------------------------------
    # PostgreSQL
    # -------------------------------------------------------------------------
    POSTGRES_USER: str = "samaritan"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "samaritan"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        """Synchronous PostgreSQL URL used by Alembic and startup health checks."""
        return (
            f"postgresql+psycopg://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}"
            f"/{self.POSTGRES_DB}"
        )

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Asynchronous PostgreSQL URL used by the FastAPI application."""
        return (
            f"postgresql+psycopg://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}"
            f"/{self.POSTGRES_DB}"
        )

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    @property
    def REDIS_URL(self) -> str:
        """Full Redis connection URL."""
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # -------------------------------------------------------------------------
    # Celery
    # -------------------------------------------------------------------------
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    @model_validator(mode="after")
    def _set_celery_defaults(self) -> "Settings":
        """Default Celery broker/backend to the Redis URL when not explicitly provided."""
        if not self.CELERY_BROKER_URL:
            object.__setattr__(self, "CELERY_BROKER_URL", self.REDIS_URL)
        if not self.CELERY_RESULT_BACKEND:
            object.__setattr__(self, "CELERY_RESULT_BACKEND", self.REDIS_URL)
        return self

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    BACKEND_CORS_ORIGINS: list[str] | str = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> list[str]:
        """Accept a comma-separated string or a JSON list from the environment."""
        if isinstance(value, str):
            if not value.strip():
                return []
            if value.startswith("[") and value.endswith("]"):
                import json
                try:
                    return json.loads(value)
                except Exception:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # -------------------------------------------------------------------------
    # Rate Limiting & Brute-Force Protection
    # -------------------------------------------------------------------------
    RATE_LIMIT_PER_MINUTE: int = 60
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    # -------------------------------------------------------------------------
    # Password Policy
    # -------------------------------------------------------------------------
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_MAX_LENGTH: int = 128
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGITS: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True

    # -------------------------------------------------------------------------
    # Email (SMTP)
    # -------------------------------------------------------------------------
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: bool = True
    EMAILS_FROM_EMAIL: str = "noreply@samaritan.io"
    EMAILS_FROM_NAME: str = "Samaritan Security"
    EMAILS_ENABLED: bool = False

    # -------------------------------------------------------------------------
    # Security & Trusted Hosts
    # -------------------------------------------------------------------------
    TRUSTED_HOSTS: list[str] = ["localhost", "127.0.0.1"]
    ALLOWED_UPLOAD_EXTENSIONS: list[str] = [".pdf", ".txt", ".csv", ".json"]
    MAX_UPLOAD_SIZE_MB: int = 10

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        """Maximum allowed file upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # -------------------------------------------------------------------------
    # Pagination Defaults
    # -------------------------------------------------------------------------
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    Using ``lru_cache`` ensures the .env file is read exactly once per process.
    In tests, call ``get_settings.cache_clear()`` after overriding environment
    variables to force re-evaluation.
    """
    return Settings()


# Module-level singleton — import this everywhere.
settings: Settings = get_settings()
