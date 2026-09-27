import logging
from typing import Any, AsyncGenerator, Dict
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool
from backend.app.config import settings
from backend.db.models import Base

logger = logging.getLogger("cachemind.db")


def create_engine_for_url(database_url: str | None = None, **kwargs: Any) -> AsyncEngine:
    """
    Constructs a SQLAlchemy AsyncEngine configured appropriately for the underlying database dialect.
    Applies enterprise connection pooling for PostgreSQL while maintaining lightweight compatibility for SQLite.
    """
    url = database_url or settings.DATABASE_URL
    is_sqlite = url.startswith("sqlite")
    is_memory = ":memory:" in url

    echo = kwargs.pop("echo", settings.DB_ECHO or (settings.LOG_LEVEL.upper() == "DEBUG"))
    engine_kwargs: Dict[str, Any] = {
        "echo": echo,
        "future": True,
    }

    if is_sqlite:
        connect_args = kwargs.pop("connect_args", {"check_same_thread": False})
        engine_kwargs["connect_args"] = connect_args
        if is_memory and "poolclass" not in kwargs:
            engine_kwargs["poolclass"] = StaticPool
        elif "poolclass" in kwargs:
            engine_kwargs["poolclass"] = kwargs.pop("poolclass")
    else:
        # PostgreSQL / asyncpg connection pool configuration
        engine_kwargs["pool_size"] = kwargs.pop("pool_size", settings.DB_POOL_SIZE)
        engine_kwargs["max_overflow"] = kwargs.pop("max_overflow", settings.DB_MAX_OVERFLOW)
        engine_kwargs["pool_timeout"] = kwargs.pop("pool_timeout", settings.DB_POOL_TIMEOUT)
        engine_kwargs["pool_recycle"] = kwargs.pop("pool_recycle", settings.DB_POOL_RECYCLE)
        engine_kwargs["pool_pre_ping"] = kwargs.pop("pool_pre_ping", settings.DB_POOL_PRE_PING)
        if "poolclass" in kwargs:
            engine_kwargs["poolclass"] = kwargs.pop("poolclass")

    # Pass any remaining kwargs
    engine_kwargs.update(kwargs)
    return create_async_engine(url, **engine_kwargs)


# Application Singleton Engine and SessionMaker
engine: AsyncEngine = create_engine_for_url(settings.DATABASE_URL)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def get_engine() -> AsyncEngine:
    """Returns the current application engine."""
    return engine


def set_engine(new_engine: AsyncEngine) -> None:
    """Updates the singleton engine and re-binds AsyncSessionLocal."""
    global engine, AsyncSessionLocal
    engine = new_engine
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


def get_pool_status() -> Dict[str, Any]:
    """Inspects connection pool metrics for observability and health endpoints."""
    pool = engine.pool
    is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    if is_sqlite:
        return {
            "type": "sqlite",
            "size": 1,
            "checked_in": 1,
            "checked_out": 0,
            "overflow": 0,
        }

    try:
        return {
            "type": pool.__class__.__name__,
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
    except Exception as exc:
        return {
            "type": pool.__class__.__name__,
            "status": "active",
            "error": str(exc),
        }


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing a transactional async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables for testing or development."""
    if settings.AUTO_RUN_MIGRATIONS:
        try:
            logger.info("AUTO_RUN_MIGRATIONS is enabled. Running Alembic migrations...")
            from alembic import command
            from alembic.config import Config
            alembic_cfg = Config("alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic migrations completed successfully.")
            return
        except Exception as exc:
            logger.warning("Auto migration failed (%s); falling back to metadata.create_all", exc)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Gracefully dispose of all pooled database connections."""
    await engine.dispose()
