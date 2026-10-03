import pytest
from backend.app.config import Settings


def test_development_mode_allows_defaults():
    """Development mode should pass validation without error even with default settings."""
    cfg = Settings(
        ENVIRONMENT="development",
        ADMIN_MASTER_KEY="cm_admin_master_secret_key_9999999999999999",
        DATABASE_URL="sqlite+aiosqlite:///./cachemind.db",
        CACHE_BACKEND="memory",
        VECTOR_BACKEND="memory",
        ALLOW_MOCK_PROVIDERS=True,
        ALLOW_MOCK_EMBEDDINGS=True,
    )
    # Should not raise
    cfg.validate_production_configuration()


def test_test_mode_allows_defaults():
    """Test mode should pass validation without error."""
    cfg = Settings(
        ENVIRONMENT="test",
        ADMIN_MASTER_KEY="cm_admin_master_secret_key_9999999999999999",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        CACHE_BACKEND="memory",
        VECTOR_BACKEND="memory",
        ALLOW_MOCK_PROVIDERS=True,
        ALLOW_MOCK_EMBEDDINGS=True,
    )
    cfg.validate_production_configuration()


def test_production_mode_rejects_insecure_defaults():
    """Production mode must fail when insecure defaults are configured."""
    cfg = Settings(
        ENVIRONMENT="production",
        ADMIN_MASTER_KEY="cm_admin_master_secret_key_9999999999999999",
        DATABASE_URL="sqlite+aiosqlite:///./cachemind.db",
        CACHE_BACKEND="memory",
        VECTOR_BACKEND="memory",
        ALLOW_MOCK_PROVIDERS=True,
        ALLOW_MOCK_EMBEDDINGS=True,
        OPENAI_API_KEY=None,
        ANTHROPIC_API_KEY=None,
    )
    with pytest.raises(ValueError) as excinfo:
        cfg.validate_production_configuration()

    err = str(excinfo.value)
    assert "ADMIN_MASTER_KEY must be a cryptographically secure random secret" in err
    assert "DATABASE_URL cannot use SQLite in production" in err
    assert "CACHE_BACKEND cannot be 'memory' in production" in err
    assert "VECTOR_BACKEND cannot be 'memory' in production" in err
    assert "No upstream LLM provider credentials configured" in err
    assert "ALLOW_MOCK_PROVIDERS must be false in production mode" in err
    assert "ALLOW_MOCK_EMBEDDINGS must be false in production mode" in err


def test_production_mode_passes_with_valid_config():
    """Production mode must succeed when proper production configuration is provided."""
    cfg = Settings(
        ENVIRONMENT="production",
        ADMIN_MASTER_KEY="cm_sec_prod_master_admin_key_999999999999999999999999",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/cachemind_prod",
        CACHE_BACKEND="redis",
        REDIS_URL="redis://localhost:6379/0",
        VECTOR_BACKEND="pgvector",
        ALLOW_MOCK_PROVIDERS=False,
        ALLOW_MOCK_EMBEDDINGS=False,
        OPENAI_API_KEY="sk-proj-prod-real-api-key-here",
    )
    # Should not raise
    cfg.validate_production_configuration()


def test_verification_mode_allows_mock_flags():
    """Verification mode should pass validation while allowing mock provider flags for staging verification."""
    cfg = Settings(
        ENVIRONMENT="verification",
        ADMIN_MASTER_KEY="cm_verify_master_sec_09a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/cachemind_verify",
        CACHE_BACKEND="redis",
        REDIS_URL="redis://localhost:6379/0",
        VECTOR_BACKEND="pgvector",
        ALLOW_MOCK_PROVIDERS=True,
        ALLOW_MOCK_EMBEDDINGS=True,
    )
    cfg.validate_production_configuration()


def test_init_db_does_not_create_all_in_production_or_verification(monkeypatch):
    """Production and verification gateway workers must NEVER call create_all."""
    import backend.db.session as db_session_mod
    from backend.db.models import Base

    for env in ("production", "verification"):
        monkeypatch.setattr(db_session_mod.settings, "ENVIRONMENT", env)
        monkeypatch.setattr(db_session_mod.settings, "AUTO_RUN_MIGRATIONS", False)

        called = False

        def fake_create_all(conn):
            nonlocal called
            called = True

        monkeypatch.setattr(Base.metadata, "create_all", fake_create_all)

        import asyncio
        asyncio.run(db_session_mod.init_db())

        assert called is False, f"create_all must not be called in {env}"


def test_init_db_calls_create_all_in_development(monkeypatch):
    """Development environment preserves explicit create_all behaviour."""
    import backend.db.session as db_session_mod
    from backend.db.models import Base

    monkeypatch.setattr(db_session_mod.settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(db_session_mod.settings, "AUTO_RUN_MIGRATIONS", False)

    called = False

    def fake_create_all(conn):
        nonlocal called
        called = True

    monkeypatch.setattr(Base.metadata, "create_all", fake_create_all)

    import asyncio
    asyncio.run(db_session_mod.init_db())

    assert called is True, "create_all should be called in development"

