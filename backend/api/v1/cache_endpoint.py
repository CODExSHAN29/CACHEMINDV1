import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from backend.auth.dependencies import get_authenticated_identity
from backend.auth.identity import AuthenticatedIdentity
from backend.caching.invalidation import (
    CacheKeyInspection,
    CacheManagementService,
    CachePurgeRequest,
    CachePurgeResult,
)
from backend.caching.warmer import CacheWarmer, WarmBatchRequest, WarmBatchResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/cache", tags=["Cache Lifecycle & Management"])


@router.delete("/keys/{exact_request_hash}")
async def delete_cache_key(
    exact_request_hash: str,
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> JSONResponse:
    """
    Surgically delete an exact cache entry by its exact request hash from both L1 and L2 caches.
    """
    deleted = await CacheManagementService.delete_exact_key(
        project_id=identity.project_id,
        exact_request_hash=exact_request_hash,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "deleted": deleted,
            "exact_request_hash": exact_request_hash,
            "project_id": identity.project_id,
        },
    )


@router.get("/inspect/{exact_request_hash}", response_model=CacheKeyInspection)
async def inspect_cache_key(
    exact_request_hash: str,
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> CacheKeyInspection:
    """
    Inspects cache metadata, remaining TTL, hit count, and payload preview for a specific cache key.
    """
    inspection = await CacheManagementService.inspect_key(
        project_id=identity.project_id,
        exact_request_hash=exact_request_hash,
    )
    if not inspection.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cache key {exact_request_hash} not found in project {identity.project_id}",
        )
    return inspection


@router.get("/keys")
async def list_cache_keys(
    limit: int = Query(default=100, ge=1, le=1000),
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> Dict[str, Any]:
    """
    Lists cached exact request hash keys under the authenticated project.
    """
    keys = await CacheManagementService.list_keys(
        project_id=identity.project_id,
        limit=limit,
    )
    return {
        "project_id": identity.project_id,
        "count": len(keys),
        "keys": keys,
    }


@router.post("/purge", response_model=CachePurgeResult)
async def purge_cache(
    req: CachePurgeRequest,
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> CachePurgeResult:
    """
    Purges cache entries belonging to the authenticated tenant/project,
    optionally scoped by model, namespace, or tags.
    """
    target_project = req.project_id or identity.project_id
    if target_project != identity.project_id and not identity.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot purge cache for a foreign project without admin privileges.",
        )

    result = await CacheManagementService.purge_cache(
        tenant_id=identity.tenant_id,
        project_id=target_project,
        model=req.model,
        namespace=req.namespace,
        tags=req.tags,
    )
    return result


@router.post("/warm", response_model=WarmBatchResult)
async def warm_cache(
    req: WarmBatchRequest,
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> WarmBatchResult:
    """
    Pre-warms / seeds L1 and L2 caches with pre-computed Q&A / prompt-completion pairs.
    """
    target_project = req.project_id or identity.project_id
    if target_project != identity.project_id and not identity.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot seed cache for a foreign project without admin privileges.",
        )

    result = await CacheWarmer.warm_cache(
        tenant_id=identity.tenant_id,
        project_id=target_project,
        items=req.items,
    )
    return result
