import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from backend.app.config import settings
from backend.api.v1.admin import router as admin_router
from backend.api.v1.analytics import router as analytics_router
from backend.api.v1.billing import router as billing_router
from backend.api.v1.cache_endpoint import router as cache_router
from backend.api.v1.chat import router as chat_router
from backend.api.v1.dashboard import router as dashboard_router
from backend.api.v1.health import router as health_router
from backend.api.v1.metrics_endpoint import router as metrics_router
from backend.api.v1.models_endpoint import router as models_router
from backend.auth.keys import hash_api_key
from backend.db.models import APIKey, Project, Tenant
from backend.db.session import AsyncSessionLocal, close_db, init_db
from backend.providers.factory import get_provider

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cachemind")


async def seed_development_fixtures() -> None:
    """Seeds a default development tenant, project, and API key if they don't already exist."""
    async with AsyncSessionLocal() as session:
        # Check if default tenant exists
        res = await session.execute(
            select(Tenant).where(Tenant.id == settings.DEV_TENANT_ID)
        )
        tenant = res.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                id=settings.DEV_TENANT_ID,
                name="Default Development Tenant",
                is_active=True,
            )
            session.add(tenant)
            await session.commit()

        # Check if default project exists
        res = await session.execute(
            select(Project).where(Project.id == settings.DEV_PROJECT_ID)
        )
        project = res.scalar_one_or_none()
        if not project:
            project = Project(
                id=settings.DEV_PROJECT_ID,
                tenant_id=tenant.id,
                name="Default Development Project",
                is_active=True,
            )
            session.add(project)
            await session.commit()

        # Check if default API key exists
        dev_key_hash = hash_api_key(settings.DEV_API_KEY)
        res = await session.execute(
            select(APIKey).where(APIKey.key_hash == dev_key_hash)
        )
        api_key = res.scalar_one_or_none()
        if not api_key:
            api_key = APIKey(
                project_id=project.id,
                key_prefix=settings.DEV_API_KEY[:16],
                key_hash=dev_key_hash,
                name="Default Development Key",
                role="admin",
                is_active=True,
            )
            session.add(api_key)
            await session.commit()
            logger.info("Seeded default development API Key: %s", settings.DEV_API_KEY[:16] + "...")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and graceful shutdown."""
    logger.info("Starting CacheMind Gateway (Environment: %s)...", settings.ENVIRONMENT)
    # Fail-closed production configuration validation
    settings.validate_production_configuration()
    await init_db()
    if settings.ENVIRONMENT == "development":
        await seed_development_fixtures()

    # --- PHASE 1: FastEmbed Startup Warm-Up ---
    if settings.EMBEDDING_WARMUP_ENABLED:
        logger.info("Initializing embedding engine warmup...")
        from backend.semantic.embedding import get_embedding_engine
        import time
        start = time.perf_counter()
        engine = get_embedding_engine()
        # Warmup happens lazily on first embed() call, but we trigger it here
        # to remove cold-start from the first user request
        try:
            # Emit one deterministic warmup embedding
            _ = await engine.embed(settings.EMBEDDING_WARMUP_TEXT)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info("Embedding warmup completed in %.2fms", duration_ms)
        except Exception as e:
            logger.error("Embedding warmup failed: %s", str(e))
            # Do not fail startup; first user request will pay cold-start cost

    yield
    logger.info("Shutting down CacheMind Gateway...")
    provider = get_provider()
    await provider.close()
    await close_db()


app = FastAPI(
    title="CacheMind Gateway",
    description="Safe, Measurable Semantic & Exact Caching Gateway for LLM APIs",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for open SDK / Web integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(chat_router)
app.include_router(models_router)
app.include_router(analytics_router)
app.include_router(cache_router)
app.include_router(admin_router)
app.include_router(billing_router)
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(dashboard_router)


@app.get("/", tags=["Gateway Info"])
async def root():
    return {
        "service": "CacheMind Gateway",
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health",
        "frontend_dashboard_url": "http://localhost:3000",
        "version": "0.1.0",
        "description": "Safe, Sub-Millisecond Semantic & Exact Caching Gateway for LLM APIs",
    }
