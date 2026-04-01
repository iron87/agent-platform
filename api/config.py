from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SECRETS = {
    "change-me",
    "sk-2brain-change-me",
    "sk-litellm-master-change-me",
    "sk-agent-platform-internal",
    "pk-change-me",
    "sk-change-me",
}


class Settings(BaseSettings):
    """Centralized runtime configuration with strict env validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="forbid",
    )

    ENV: Literal["development", "test", "staging", "production"] = "development"
    LOG_LEVEL: Literal["debug", "info", "warning", "error", "critical"] = "info"

    API_HOST: str = "0.0.0.0"
    API_PORT: int = Field(default=8000, ge=1, le=65535)
    API_PREFIX: str = "/api/v1"
    AGENT_API_KEY: str

    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = Field(default=5432, ge=1, le=65535)
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    DATABASE_URL: str

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = Field(default=6379, ge=1, le=65535)
    REDIS_PASSWORD: str
    REDIS_URL: str

    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = Field(default=6333, ge=1, le=65535)
    QDRANT_URL: str

    LITELLM_BASE_URL: str
    LITELLM_API_KEY: str
    LITELLM_MASTER_KEY: str

    LOCAL_LLM_API_BASE: str
    LOCAL_LLM_API_KEY: str = "not-required"
    LOCAL_DEFAULT_MODEL: str
    LOCAL_FAST_MODEL: str
    LOCAL_EMBEDDING_MODEL: str
    LOCAL_EMBEDDING_API_BASE: str
    LOCAL_EMBEDDING_API_KEY: str = "not-required"

    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    LITELLM_BUDGET_DEFAULT: float = Field(default=300.0, ge=0.0)
    LITELLM_BUDGET_FAST: float = Field(default=500.0, ge=0.0)
    LITELLM_BUDGET_EMBEDDING: float = Field(default=100.0, ge=0.0)
    LITELLM_BUDGET_DURATION: str = "30d"
    LITELLM_TENANT_BUDGET_TOTAL: float = Field(default=1000.0, ge=0.0)
    LITELLM_TENANT_BUDGET_DURATION: str = "30d"

    LANGFUSE_HOST: str
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_SECRET_KEY: str

    MINIO_ROOT_USER: str = "minio"
    MINIO_ROOT_PASSWORD: str
    CLICKHOUSE_DB: str = "default"
    CLICKHOUSE_USER: str = "default"
    CLICKHOUSE_PASSWORD: str

    RQ_QUEUE_NAME: str = "agent_jobs"
    JOB_TIMEOUT_SECONDS: int = Field(default=60, ge=1)
    WORKER_TTL_SECONDS: int = Field(default=420, ge=1)
    SESSION_TTL_SECONDS: int = Field(default=86400, ge=1)
    HITL_TIMEOUT_SECONDS: int = Field(default=3600, ge=1)

    GUARDRAILS_ENABLED: bool = True
    LANGFUSE_ENABLED: bool = True

    CADDY_EMAIL: str = "devnull@example.com"

    @field_validator("API_PREFIX")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("API_PREFIX must start with '/'.")
        return value.rstrip("/") or "/"

    @field_validator(
        "DATABASE_URL",
        "REDIS_URL",
        "QDRANT_URL",
        "LITELLM_BASE_URL",
        "LOCAL_LLM_API_BASE",
        "LOCAL_EMBEDDING_API_BASE",
        "LANGFUSE_HOST",
    )
    @classmethod
    def validate_urls(cls, value: str) -> str:
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {value}")
        return value

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url_scheme(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"postgresql", "postgresql+asyncpg"}:
            raise ValueError("DATABASE_URL must use postgresql or postgresql+asyncpg scheme.")
        return value

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url_scheme(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"redis", "rediss"}:
            raise ValueError("REDIS_URL must use redis or rediss scheme.")
        return value

    @field_validator(
        "AGENT_API_KEY",
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "LITELLM_API_KEY",
        "LITELLM_MASTER_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "MINIO_ROOT_PASSWORD",
        "CLICKHOUSE_PASSWORD",
    )
    @classmethod
    def reject_placeholder_secret_values(cls, value: str) -> str:
        if not value or value in _PLACEHOLDER_SECRETS:
            raise ValueError("Secret value must be set to a non-placeholder value.")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
