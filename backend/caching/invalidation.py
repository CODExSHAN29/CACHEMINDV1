import logging
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.caching.factory import get_cache_backend
from backend.caching.models import CachedResponse
from backend.semantic.factory import get_semantic_cache_service

logger = logging.getLogger(__name__)


class CachePurgeRequest(BaseModel):
    project_id: Optional[str] = None
    model: Optional[str] = None
    namespace: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class CachePurgeResult(BaseModel):
    tenant_id: str
    project_id: Optional[str] = None
    purged_l1: int = 0
    purged_l2: int = 0
    success: bool = True
    message: str = "Purge completed successfully"


class CacheKeyInspection(BaseModel):
    exact_request_hash: str
    project_id: str
    exists: bool
    provider: Optional[str] = None
    model: Optional[str] = None
    ttl_seconds: Optional[int] = None
    hit_count: int = 0
    namespace: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    response_preview: Optional[str] = None
    content_preview: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    created_at: Optional[float] = None


class CacheManagementService:
    """
    Enterprise Cache Lifecycle & Invalidation Service.
    Coordinates surgical invalidation and scoped purging across L1 exact cache
    and L2 semantic vector indices.
    """

    @classmethod
    async def delete_exact_key(
        cls, project_id: str, exact_request_hash: str
    ) -> bool:
        """
        Surgically deletes a specific exact cache key from both L1 and L2 indices.
        """
        cache_backend = get_cache_backend()
        semantic_service = get_semantic_cache_service()

        l1_deleted = await cache_backend.delete(project_id, exact_request_hash)
        l2_deleted = False
        try:
            l2_deleted = await semantic_service.backend.delete(exact_request_hash)
        except Exception as exc:
            logger.warning("Error deleting vector entry %s: %s", exact_request_hash, exc)

        return l1_deleted or l2_deleted

    @classmethod
    async def purge_cache(
        cls,
        tenant_id: str,
        project_id: str,
        model: Optional[str] = None,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> CachePurgeResult:
        """
        Purges cached entries belonging to a tenant/project, optionally filtered
        by model, namespace, or tags.
        """
        cache_backend = get_cache_backend()
        semantic_service = get_semantic_cache_service()

        purged_l1 = 0
        purged_l2 = 0

        # Purge L1 Exact Cache
        try:
            if model or namespace or tags:
                keys = await cache_backend.list_keys(project_id, limit=10000)
                for k in keys:
                    cached_item = await cache_backend.get(project_id, k)
                    if not cached_item:
                        continue
                    matches = True
                    if model and cached_item.model != model:
                        matches = False
                    if namespace and cached_item.namespace != namespace:
                        matches = False
                    if tags:
                        item_tags = set(cached_item.tags or [])
                        if not set(tags).issubset(item_tags):
                            matches = False
                    if matches:
                        if await cache_backend.delete(project_id, k):
                            purged_l1 += 1
            else:
                purged_l1 = await cache_backend.purge_project(project_id)
        except Exception as exc:
            logger.error("Error purging L1 cache for project %s: %s", project_id, exc)

        # Purge L2 Semantic Vector Backend
        try:
            purged_l2 = await semantic_service.backend.delete_by_tenant(tenant_id)
            if purged_l2 == 0:
                vector_stats = await semantic_service.backend.get_stats()
                scopes = vector_stats.get("scopes", {})
                for sh in list(scopes.keys()):
                    del_count = await semantic_service.backend.delete_by_scope(sh)
                    purged_l2 += del_count
        except Exception as exc:
            logger.error("Error purging L2 vector backend for project %s: %s", project_id, exc)

        return CachePurgeResult(
            tenant_id=tenant_id,
            project_id=project_id,
            purged_l1=purged_l1,
            purged_l2=purged_l2,
            success=True,
            message=f"Purged {purged_l1} L1 entries and {purged_l2} L2 semantic entries.",
        )

    @classmethod
    async def inspect_key(
        cls, project_id: str, exact_request_hash: str
    ) -> CacheKeyInspection:
        """
        Inspects metadata, TTL, hit count, and contents of a specific cached response.
        """
        cache_backend = get_cache_backend()
        cached: Optional[CachedResponse] = await cache_backend.get(
            project_id, exact_request_hash
        )

        if not cached:
            return CacheKeyInspection(
                exact_request_hash=exact_request_hash,
                project_id=project_id,
                exists=False,
            )

        preview = ""
        if cached.content:
            preview = cached.content
        else:
            payload = cached.response_payload or {}
            choices = payload.get("choices", [])
            if choices and isinstance(choices, list):
                first_choice = choices[0]
                if isinstance(first_choice, dict):
                    msg = first_choice.get("message", {})
                    content = msg.get("content", "")
                    if content:
                        preview = content[:200] + ("..." if len(content) > 200 else "")

        return CacheKeyInspection(
            exact_request_hash=exact_request_hash,
            project_id=project_id,
            exists=True,
            provider=cached.provider,
            model=cached.model,
            ttl_seconds=cached.ttl_seconds,
            hit_count=cached.hit_count,
            namespace=cached.namespace,
            tags=cached.tags or [],
            response_preview=preview,
            content_preview=preview,
            usage=(cached.response_payload or {}).get("usage"),
            created_at=cached.created_at,
        )

    @classmethod
    async def list_keys(
        cls, project_id: str, limit: int = 100
    ) -> List[str]:
        """
        Lists cached exact request hash keys for a project.
        """
        cache_backend = get_cache_backend()
        return await cache_backend.list_keys(project_id, limit=limit)
