import time
from typing import Any, Dict
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.caching.factory import get_cache_backend
from backend.db.session import AsyncSessionLocal

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Liveness probe: returns 200 if gateway process is running."""
    return {
        "status": "healthy",
        "service": "cachemind-gateway",
        "timestamp": time.time(),
    }


@router.get("/ready")
async def readiness_check() -> JSONResponse:
    """
    Readiness probe: validates database and cache backend connectivity.
    Returns 200 if all downstream dependencies are reachable, 503 otherwise.
    """
    db_ok = False
    cache_ok = False

    # Check Database
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False

    # Check Cache Backend
    try:
        cache = get_cache_backend()
        cache_ok = await cache.ping()
    except Exception:
        cache_ok = False

    status_code = (
        status.HTTP_200_OK if (db_ok and cache_ok) else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if (db_ok and cache_ok) else "not_ready",
            "database": "connected" if db_ok else "disconnected",
            "cache": "connected" if cache_ok else "disconnected",
            "timestamp": time.time(),
        },
    )
