import pytest
from sqlalchemy.pool import NullPool, StaticPool, QueuePool, AsyncAdaptedQueuePool
from backend.app.config import Settings, settings
from backend.db.session import create_engine_for_url, get_pool_status


def test_database_url_normalization():
    # Test normalization of postgres schemes
    s1 = Settings(DATABASE_URL="postgres://user:pass@localhost:5432/db")
    assert s1.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost:5432/db"

    s2 = Settings(DATABASE_URL="postgresql://user:pass@localhost:5432/db")
    assert s2.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost:5432/db"

    s3 = Settings(DATABASE_URL="sqlite:///./test.db")
    assert s3.DATABASE_URL == "sqlite+aiosqlite:///./test.db"

    s4 = Settings(DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db")
    assert s4.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost:5432/db"


def test_sqlite_engine_creation():
    engine_mem = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    assert engine_mem.url.drivername == "sqlite+aiosqlite"
    assert isinstance(engine_mem.pool, StaticPool)

    engine_file = create_engine_for_url("sqlite+aiosqlite:///./test_pool.db", poolclass=NullPool)
    assert engine_file.url.drivername == "sqlite+aiosqlite"
    assert isinstance(engine_file.pool, NullPool)


def test_postgresql_engine_configuration():
    # Create postgresql engine with custom pool parameters
    engine_pg = create_engine_for_url(
        "postgresql+asyncpg://user:pass@localhost:5432/db",
        pool_size=15,
        max_overflow=5,
        pool_timeout=20.0,
        pool_recycle=900,
        pool_pre_ping=True,
    )
    assert engine_pg.url.drivername == "postgresql+asyncpg"
    assert isinstance(engine_pg.pool, (QueuePool, AsyncAdaptedQueuePool))
    assert engine_pg.pool.size() == 15


def test_pool_status_inspection():
    status = get_pool_status()
    assert "type" in status
    assert "checked_in" in status
    assert "checked_out" in status
    assert "overflow" in status
