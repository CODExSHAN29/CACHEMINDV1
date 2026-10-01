import time
from typing import Any, Dict
from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.app.config import settings
from backend.caching.factory import get_cache_backend
from backend.db.session import AsyncSessionLocal
from backend.semantic.embedding import get_embedding_engine

router = APIRouter(tags=["Health & Probes"])


@router.get("/health/live", summary="Liveness probe")
@router.get("/live", summary="Liveness probe alias")
async def liveness_check() -> Dict[str, Any]:
    """
    Lightweight Kubernetes liveness probe.
    Returns 200 OK as long as the process is running and accepting event loop cycles.
    Does NOT check external dependencies to avoid false-positive restarts during transient outages.
    """
    return {
        "status": "healthy",
        "service": "cachemind-gateway",
        "probe": "liveness",
        "timestamp": time.time(),
    }


@router.get("/health/ready", summary="Readiness probe")
@router.get("/ready", summary="Readiness probe alias")
async def readiness_check() -> JSONResponse:
    """
    Comprehensive Kubernetes readiness probe.
    Validates that the service is ready to accept user traffic:
    1. Database connection pool (SELECT 1)
    2. L1 Cache backend responsiveness (ping)
    3. L2 Embedding engine availability
    4. Provider configuration validity (without making paid LLM calls)

    Returns HTTP 200 if all critical components are operational, HTTP 503 if degraded/not ready.
    """
    components: Dict[str, Dict[str, Any]] = {}
    is_ready = True

    # 1. Database Check
    db_start = time.perf_counter()
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_duration = (time.perf_counter() - db_start) * 1000
        components["database"] = {
            "status": "healthy",
            "latency_ms": round(db_duration, 2),
            "url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else settings.DATABASE_URL.split("///")[-1],
        }
    except Exception as e:
        is_ready = False
        components["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # 2. Cache Backend Check (L1)
    cache_start = time.perf_counter()
    try:
        cache = get_cache_backend()
        cache_ok = await cache.ping() if hasattr(cache, "ping") else True
        cache_duration = (time.perf_counter() - cache_start) * 1000
        if cache_ok:
            components["cache_backend"] = {
                "status": "healthy",
                "backend": settings.CACHE_BACKEND,
                "latency_ms": round(cache_duration, 2),
            }
        else:
            is_ready = False
            components["cache_backend"] = {
                "status": "unhealthy",
                "backend": settings.CACHE_BACKEND,
                "error": "Cache backend ping returned False",
            }
    except Exception as e:
        is_ready = False
        components["cache_backend"] = {
            "status": "unhealthy",
            "backend": settings.CACHE_BACKEND,
            "error": str(e),
        }

    # 3. Embedding Engine & Vector Index (L2)
    embed_start = time.perf_counter()
    try:
        engine = get_embedding_engine()
        # Non-blocking state inspection: verify engine is initialized
        embed_duration = (time.perf_counter() - embed_start) * 1000
        components["embedding_engine"] = {
            "status": "healthy",
            "model": engine.model_name,
            "dim": engine.embedding_dim,
            "warmup_done": getattr(engine, "_warmup_done", False),
            "latency_ms": round(embed_duration, 2),
        }
    except Exception as e:
        is_ready = False
        components["embedding_engine"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # 4. Provider Configuration Readiness (Check keys exist without external network call)
    configured_providers = []
    if settings.OPENAI_API_KEY:
        configured_providers.append("openai")
    if settings.ANTHROPIC_API_KEY:
        configured_providers.append("anthropic")
    if settings.OLLAMA_BASE_URL:
        configured_providers.append("ollama")
    if settings.ALLOW_MOCK_PROVIDERS:
        configured_providers.append("mock")

    if not configured_providers and settings.ENVIRONMENT == "production":
        is_ready = False
        components["upstream_providers"] = {
            "status": "unhealthy",
            "error": "No LLM providers configured in production environment",
        }
    else:
        components["upstream_providers"] = {
            "status": "healthy",
            "configured": configured_providers,
        }

    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "not_ready",
            "environment": settings.ENVIRONMENT,
            "timestamp": time.time(),
            "components": components,
        },
    )


@router.get("/health", summary="General Health Status (Legacy)")
async def health_check() -> Dict[str, Any]:
    """
    Backward-compatible general health endpoint.
    """
    return {
        "status": "healthy",
        "service": "cachemind-gateway",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
        "timestamp": time.time(),
    }
