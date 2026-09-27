from typing import Literal
from pydantic import Field, field_validator
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
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./cachemind.db",
        description="Database connection URL",
    )
    DB_POOL_SIZE: int = Field(default=20, description="Base number of connections kept in pool")
    DB_MAX_OVERFLOW: int = Field(default=10, description="Maximum overflow connections beyond pool_size")
    DB_POOL_TIMEOUT: float = Field(default=30.0, description="Seconds to wait before timing out on pool checkout")
    DB_POOL_RECYCLE: int = Field(default=1800, description="Recycle connections after N seconds")
    DB_POOL_PRE_PING: bool = Field(default=True, description="Verify connection liveness with SELECT 1 on checkout")
    DB_ECHO: bool = Field(default=False, description="Echo all SQL statements to stdout")
    AUTO_RUN_MIGRATIONS: bool = Field(default=False, description="Automatically execute Alembic migrations on startup")

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        # Normalize standard postgresql:// schemes to asyncpg driver
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and not v.startswith("postgresql+"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        # Normalize standard sqlite:// schemes to aiosqlite driver
        if v.startswith("sqlite://") and not v.startswith("sqlite+"):
            return v.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return v

    # Cache Backend (L1)
    CACHE_BACKEND: Literal["memory", "redis"] = "memory"
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CLUSTER_MODE: bool = False
    REDIS_SENTINEL_HOSTS: str | None = None
    REDIS_SENTINEL_MASTER: str = "mymaster"
    REDIS_PASSWORD: str | None = None
    REDIS_SSL: bool = False
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: float = 2.0
    DEFAULT_CACHE_TTL_SECONDS: int = 86400  # 24 hours

    # Vector Storage Backend (L2 Semantic Cache)
    VECTOR_BACKEND: Literal["memory", "pgvector", "qdrant"] = "memory"
    VECTOR_DIMENSION: int = 384
    VECTOR_SIMILARITY_THRESHOLD: float = 0.92
    PGVECTOR_INDEX_TYPE: Literal["hnsw", "ivfflat", "exact"] = "hnsw"
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "cachemind_semantic_cache"

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
