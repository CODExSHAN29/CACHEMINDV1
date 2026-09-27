from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Environment
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./cachemind.db"

    # Cache Backend
    CACHE_BACKEND: Literal["memory", "redis"] = "memory"
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_SOCKET_TIMEOUT: float = 2.0
    DEFAULT_CACHE_TTL_SECONDS: int = 86400  # 24 hours

    # Upstream Provider Configuration
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com/v1"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    UPSTREAM_TIMEOUT_SECONDS: float = 30.0
    UPSTREAM_MAX_CONNECTIONS: int = 100
    UPSTREAM_MAX_KEEPALIVE_CONNECTIONS: int = 20

    # Resilience & Circuit Breaker
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 3
    CIRCUIT_BREAKER_RECOVERY_SECONDS: float = 30.0

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    DEFAULT_RPM_LIMIT: int = 120
    DEFAULT_TPM_LIMIT: int = 100_000

    # Security & PII Sanitization
    PII_MASKING_ENABLED: bool = True
    PII_MASKING_MODE: Literal["mask", "block", "passthrough"] = "mask"

    # Master Admin Key for /v1/admin/* management
    ADMIN_MASTER_KEY: str = "cm_admin_master_secret_key_9999999999999999"

    # Development / Testing Keys
    DEV_TENANT_ID: str = "tenant_default"
    DEV_PROJECT_ID: str = "proj_default"
    DEV_API_KEY: str = "cm_live_development_test_key_000000000000000000000000"


settings = Settings()
