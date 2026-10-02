import os
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from backend.app.config import settings
from backend.db.models import Tenant, Project, APIKey, RequestLog
from backend.db.session import create_engine_for_url, AsyncSessionLocal
from scripts.migrate_and_seed import verify_connectivity, seed_default_dev_fixtures


@pytest.mark.asyncio
async def test_alembic_migration_lifecycle(tmp_path):
    # Test running migrations against an isolated temporary SQLite database
    db_file = tmp_path / "test_migration.db"
    test_db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    ini_path = os.path.join(repo_root, "alembic.ini")
    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("script_location", os.path.join(repo_root, "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)

    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    # 2. Verify tables exist and can be queried via async engine
    engine = create_engine_for_url(test_db_url)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = {row[0] for row in res.fetchall()}
        assert "users" in tables
        assert "tenants" in tables
        assert "tenant_memberships" in tables
        assert "projects" in tables
        assert "api_keys" in tables
        assert "sessions" in tables
        assert "request_logs" in tables
        assert "semantic_cache_entries" in tables
        assert "alembic_version" in tables

    # 3. Downgrade to base
    command.downgrade(alembic_cfg, "base")

    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = {row[0] for row in res.fetchall()}
        assert "users" not in tables
        assert "tenants" not in tables
        assert "tenant_memberships" not in tables
        assert "projects" not in tables
        assert "api_keys" not in tables
        assert "sessions" not in tables
        assert "request_logs" not in tables
        assert "semantic_cache_entries" not in tables

    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_and_seed_cli_helpers(db_session):
    # Verify connectivity
    is_connected = await verify_connectivity()
    assert is_connected is True

    # Seed fixtures
    await seed_default_dev_fixtures()

    import backend.db.session as db_session_mod
    async with db_session_mod.AsyncSessionLocal() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.id == settings.DEV_TENANT_ID)
        )
        tenant = result.scalar_one_or_none()
        assert tenant is not None
        assert tenant.id == settings.DEV_TENANT_ID


@pytest.mark.asyncio
async def test_init_db_fails_closed_on_migration_error(monkeypatch):
    """
    Verifies that when AUTO_RUN_MIGRATIONS is True, any exception raised during
    Alembic migration execution is re-raised immediately to abort startup,
    rather than silently falling back to Base.metadata.create_all().
    """
    import backend.db.session as db_session_mod

    monkeypatch.setattr(settings, "AUTO_RUN_MIGRATIONS", True)

    def failing_upgrade(cfg, revision):
        raise RuntimeError("Simulated Alembic Migration Failure: Schema lock conflict")

    import alembic.command
    monkeypatch.setattr(alembic.command, "upgrade", failing_upgrade)

    with pytest.raises(RuntimeError) as exc_info:
        await db_session_mod.init_db()

    assert "Simulated Alembic Migration Failure" in str(exc_info.value)

