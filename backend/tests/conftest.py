import asyncio
import os
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.config import settings
from backend.app.main import app
from backend.auth.keys import generate_api_key
from backend.caching.factory import set_cache_backend
from backend.caching.memory import InMemoryExactCache
from backend.db.models import APIKey, Base, Project, Tenant, SemanticVectorEntry
from backend.db.session import get_db, set_engine
from backend.guardrails.arbiter import GuardrailArbiter
from backend.guardrails.volatility import VolatilityEngine
from backend.guardrails.factory import set_guardrail_arbiter, set_volatility_engine
from backend.providers.factory import set_provider
from backend.providers.mock_provider import MockProvider
from backend.providers.registry import ProviderRegistry, set_provider_registry
from backend.ratelimit.limiter import RateLimiter, get_rate_limiter, set_rate_limiter
from backend.resilience.circuit_breaker import get_circuit_breaker_registry
from backend.routing.engine import RoutingEngine, set_routing_engine
from backend.semantic.embedding import MockEmbeddingEngine
from backend.semantic.factory import SemanticCacheFactory
from backend.semantic.vector_index import VectorIndex

# Use in-memory SQLite with StaticPool for lightning fast, isolated, persistent test execution
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)
set_engine(test_engine)

TestingAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestingAsyncSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def setup_test_singletons():
    """Ensures every test runs with fresh InMemory cache, MockProvider, rate limiter, and circuit breakers."""
    mem_cache = InMemoryExactCache()
    mock_prov = MockProvider()
    set_cache_backend(mem_cache)
    # Reset provider and routing engine singletons
    reg = ProviderRegistry()
    reg.register("mock", mock_prov)
    reg.register("openai", mock_prov)
    reg.register("anthropic", mock_prov)
    reg.register("ollama", mock_prov)
    set_provider_registry(reg)
    set_provider(mock_prov)
    from backend.routing.engine import RoutingEngine, set_routing_engine
    set_routing_engine(RoutingEngine(provider_registry=reg))

    # Phase 2 singletons reset & mock
    mock_embed = MockEmbeddingEngine()
    vec_index = VectorIndex()
    vec_index._clear_sync()
    arbiter = GuardrailArbiter()
    volatility = VolatilityEngine()

    SemanticCacheFactory.set_embedding_engine(mock_embed)
    SemanticCacheFactory.set_vector_index(vec_index)
    SemanticCacheFactory.set_arbiter(arbiter)
    SemanticCacheFactory.set_volatility_engine(volatility)
    set_guardrail_arbiter(arbiter)
    set_volatility_engine(volatility)

    # Phase 4 singletons reset
    limiter = RateLimiter()
    set_rate_limiter(limiter)
    get_circuit_breaker_registry().reset_all()

    return mem_cache, mock_prov


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def tenant_a_fixtures(db_session: AsyncSession):
    """Creates Tenant A, Project A1, and returns (raw_key, tenant_id, project_id)."""
    tenant = Tenant(id="tenant_alpha", name="Alpha Corp", is_active=True)
    db_session.add(tenant)
    await db_session.commit()

    proj = Project(id="proj_alpha_1", tenant_id=tenant.id, name="Alpha Main App", is_active=True)
    db_session.add(proj)
    await db_session.commit()

    raw_key, key_prefix, key_hash = generate_api_key("cm_live_alpha_")
    api_key = APIKey(
        id="key_alpha_1",
        project_id=proj.id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name="Alpha Key 1",
        is_active=True,
    )
    db_session.add(api_key)
    await db_session.commit()

    return {
        "raw_key": raw_key,
        "tenant_id": tenant.id,
        "project_id": proj.id,
        "api_key_id": api_key.id,
    }


@pytest_asyncio.fixture(scope="function")
async def tenant_b_fixtures(db_session: AsyncSession):
    """Creates Tenant B, Project B1, and returns (raw_key, tenant_id, project_id)."""
    tenant = Tenant(id="tenant_beta", name="Beta Corp", is_active=True)
    db_session.add(tenant)
    await db_session.commit()

    proj = Project(id="proj_beta_1", tenant_id=tenant.id, name="Beta Main App", is_active=True)
    db_session.add(proj)
    await db_session.commit()

    raw_key, key_prefix, key_hash = generate_api_key("cm_live_beta_")
    api_key = APIKey(
        id="key_beta_1",
        project_id=proj.id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name="Beta Key 1",
        is_active=True,
    )
    db_session.add(api_key)
    await db_session.commit()

    return {
        "raw_key": raw_key,
        "tenant_id": tenant.id,
        "project_id": proj.id,
        "api_key_id": api_key.id,
    }
