import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_authenticated_identity
from backend.auth.identity import AuthenticatedIdentity
from backend.caching.invalidation import (
    CacheKeyInspection,
    CacheManagementService,
    CachePurgeRequest,
    CachePurgeResult,
)
from backend.caching.warmer import CacheWarmer, WarmBatchRequest, WarmBatchResult
from backend.db.repositories import ProjectRepository
from backend.db.session import get_db

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
    if not identity.can_write_cache:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cache write permissions required to delete cache keys.",
        )
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
    if not identity.can_read_cache:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cache read permissions required.",
        )
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
    if not identity.can_read_cache:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cache read permissions required.",
        )
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
    db: AsyncSession = Depends(get_db),
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> CachePurgeResult:
    """
    Purges cache entries belonging to the authenticated tenant/project,
    optionally scoped by model, namespace, or tags.
    """
    if not identity.can_write_cache:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cache write permissions required to purge cache.",
        )

    # Check tenant boundary
    if req.tenant_id and req.tenant_id != identity.tenant_id and not identity.is_system_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot purge cache for a foreign tenant.",
        )

    target_tenant = req.tenant_id if identity.is_system_admin and req.tenant_id else identity.tenant_id
    target_project = req.project_id or identity.project_id

    # Check project boundary
    if target_project != identity.project_id and not identity.is_system_admin:
        project_repo = ProjectRepository(db)
        project = await project_repo.get_project_by_id(target_project)
        if not project or project.tenant_id != identity.tenant_id or not project.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot purge cache for a project outside your workspace.",
            )
        if not identity.can_manage_project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Project management privileges required to purge another project's cache.",
            )

    result = await CacheManagementService.purge_cache(
        tenant_id=target_tenant,
        project_id=target_project,
        model=req.model,
        namespace=req.namespace,
        tags=req.tags,
    )
    return result


@router.post("/warm", response_model=WarmBatchResult)
async def warm_cache(
    req: WarmBatchRequest,
    db: AsyncSession = Depends(get_db),
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> WarmBatchResult:
    """
    Pre-warms / seeds L1 and L2 caches with pre-computed Q&A / prompt-completion pairs.
    """
    if not identity.can_write_cache:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cache write permissions required to warm cache.",
        )

    # Check tenant boundary
    if req.tenant_id and req.tenant_id != identity.tenant_id and not identity.is_system_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot warm cache for a foreign tenant.",
        )

    target_tenant = req.tenant_id if identity.is_system_admin and req.tenant_id else identity.tenant_id
    target_project = req.project_id or identity.project_id

    # Check project boundary
    if target_project != identity.project_id and not identity.is_system_admin:
        project_repo = ProjectRepository(db)
        project = await project_repo.get_project_by_id(target_project)
        if not project or project.tenant_id != identity.tenant_id or not project.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot warm cache for a project outside your workspace.",
            )
        if not identity.can_manage_project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Project management privileges required to warm another project's cache.",
            )

    result = await CacheWarmer.warm_cache(
        tenant_id=target_tenant,
        project_id=target_project,
        items=req.items,
    )
    return result

