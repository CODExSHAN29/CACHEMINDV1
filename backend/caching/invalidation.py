import logging
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.caching.factory import get_cache_backend
from backend.caching.models import CachedResponse
from backend.semantic.factory import get_semantic_cache_service

logger = logging.getLogger(__name__)


class CachePurgeRequest(BaseModel):
    tenant_id: Optional[str] = None
    project_id: Optional[str] = None
    model: Optional[str] = None
    namespace: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class CachePurgeResult(BaseModel):
    tenant_id: str
    project_id: Optional[str] = None
    purged_l1: int = 0
    purged_l2: int = 0
    status: str = "ok"
    success: bool = True
    message: str = "Purge completed successfully"
    purged: bool = True
    keys_purged: int = 0
    exact_keys_removed: int = 0
    semantic_vectors_removed: int = 0
    model: Optional[str] = None
    namespace: Optional[str] = None


class CacheKeyInspection(BaseModel):
    exact_request_hash: str
    key_hash: Optional[str] = None
    project_id: str
    exists: bool = False
    found: bool = False
    provider: Optional[str] = None
    model: Optional[str] = None
    ttl_seconds: Optional[int] = None
    ttl_remaining_seconds: Optional[int] = None
    hit_count: int = 0
    access_count: int = 0
    namespace: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    response_preview: Optional[str] = None
    prompt_preview: Optional[str] = None
    content_preview: Optional[str] = None
    tokens_saved: Optional[int] = None
    usage: Optional[Dict[str, int]] = None
    created_at: Optional[Any] = None
    expires_at: Optional[Any] = None
    exists_in_l1: bool = False
    exists_in_l2: bool = False
    exact_entry: Optional[Dict[str, Any]] = None
    semantic_entry: Optional[Dict[str, Any]] = None


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
        Enforces strict project authorization.
        """
        cache_backend = get_cache_backend()
        semantic_service = get_semantic_cache_service()

        l1_deleted = await cache_backend.delete(project_id, exact_request_hash)
        l2_deleted = False
        try:
            vector_entry = await semantic_service.backend.inspect_key(exact_request_hash)
            if vector_entry and vector_entry.get("project_id") == project_id:
                l2_deleted = await semantic_service.backend.delete(exact_request_hash)
            elif not vector_entry and l1_deleted:
                # If key was already purged or not indexed in L2, l1_deleted is sufficient
                pass
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

        # Purge L2 Semantic Vector Backend with strict project scoping
        try:
            purged_l2 = await semantic_service.backend.delete_by_scope_filters(
                tenant_id=tenant_id,
                project_id=project_id,
                model=model,
                namespace=namespace,
                tags=tags,
            )
        except Exception as exc:
            logger.error("Error purging L2 vector backend for project %s: %s", project_id, exc)

        return CachePurgeResult(
            tenant_id=tenant_id,
            project_id=project_id,
            purged_l1=purged_l1,
            purged_l2=purged_l2,
            status="ok",
            success=True,
            message=f"Purged {purged_l1} L1 entries and {purged_l2} L2 semantic entries.",
            purged=True,
            keys_purged=purged_l1 + purged_l2,
            exact_keys_removed=purged_l1,
            semantic_vectors_removed=purged_l2,
            model=model,
            namespace=namespace,
        )

    @classmethod
    async def inspect_key(
        cls, project_id: str, exact_request_hash: str
    ) -> CacheKeyInspection:
        """
        Inspects metadata, TTL, hit count, and contents of a specific cached response.
        Enforces strict project authorization across L1 and L2 layers.
        """
        cache_backend = get_cache_backend()
        cached: Optional[CachedResponse] = await cache_backend.get(
            project_id, exact_request_hash
        )

        if not cached:
            # Check L2 semantic vector backend for matching project_id
            semantic_service = get_semantic_cache_service()
            try:
                v_entry = await semantic_service.backend.inspect_key(exact_request_hash)
                if v_entry and v_entry.get("project_id") == project_id:
                    preview = v_entry.get("input_text") or ""
                    return CacheKeyInspection(
                        exact_request_hash=exact_request_hash,
                        key_hash=exact_request_hash,
                        project_id=project_id,
                        exists=True,
                        found=True,
                        exists_in_l1=False,
                        exists_in_l2=True,
                        exact_entry=None,
                        semantic_entry=v_entry,
                        provider=v_entry.get("provider"),
                        model=v_entry.get("model"),
                        ttl_seconds=v_entry.get("ttl_seconds"),
                        ttl_remaining_seconds=v_entry.get("ttl_seconds"),
                        hit_count=0,
                        access_count=0,
                        namespace=v_entry.get("namespace"),
                        tags=v_entry.get("tags") or [],
                        response_preview=preview,
                        prompt_preview=v_entry.get("input_text"),
                        content_preview=preview,
                        usage=None,
                        created_at=None,
                    )
            except Exception as exc:
                logger.warning(
                    "Error inspecting L2 vector entry %s for project %s: %s",
                    exact_request_hash,
                    project_id,
                    exc,
                )

            return CacheKeyInspection(
                exact_request_hash=exact_request_hash,
                key_hash=exact_request_hash,
                project_id=project_id,
                exists=False,
                found=False,
                exists_in_l1=False,
                exists_in_l2=False,
                exact_entry=None,
                semantic_entry=None,
                ttl_remaining_seconds=None,
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

        semantic_service = get_semantic_cache_service()
        v_entry = None
        try:
            v_entry = await semantic_service.backend.inspect_key(exact_request_hash)
            if v_entry and v_entry.get("project_id") != project_id:
                v_entry = None
        except Exception:
            pass

        return CacheKeyInspection(
            exact_request_hash=exact_request_hash,
            key_hash=exact_request_hash,
            project_id=project_id,
            exists=True,
            found=True,
            exists_in_l1=True,
            exists_in_l2=v_entry is not None,
            exact_entry=cached.response_payload if cached else None,
            semantic_entry=v_entry,
            provider=cached.provider,
            model=cached.model,
            ttl_seconds=cached.ttl_seconds,
            ttl_remaining_seconds=cached.ttl_seconds,
            hit_count=cached.hit_count,
            access_count=cached.hit_count,
            namespace=cached.namespace,
            tags=cached.tags or [],
            response_preview=preview,
            prompt_preview=None,
            content_preview=preview,
            tokens_saved=(cached.response_payload or {}).get("usage", {}).get("total_tokens") if cached.response_payload else None,
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
