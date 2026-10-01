"""
Semantic Cache Factory — Provides singleton instances for semantic caching components.

Manages the lifecycle of EmbeddingEngine, SemanticCacheBackend (VectorIndex / PgVector / Qdrant),
GuardrailArbiter, and VolatilityEngine, enabling dependency injection for testing and
authoritative configuration.
"""

import logging
from typing import Any, Dict, List, Optional

from .embedding import EmbeddingEngine, get_embedding_engine, set_embedding_engine
from .vector_index import SemanticCandidate, VectorIndex, get_vector_index, set_vector_index
from .backend import SemanticCacheBackend
from backend.app.config import settings

logger = logging.getLogger("cachemind.semantic.factory")

try:
    from .pgvector_backend import PgVectorSemanticBackend
except Exception:
    PgVectorSemanticBackend = None  # type: ignore

try:
    from .qdrant_backend import QdrantSemanticBackend
except Exception:
    QdrantSemanticBackend = None  # type: ignore

_cached_vector_backend: Optional[SemanticCacheBackend] = None
_cached_backend_type: Optional[str] = None
_cached_semantic_service: Optional["SemanticCacheService"] = None


class SemanticCacheFactory:
    """
    Factory for creating and managing semantic cache service components.
    Delegates directly to module-level singleton providers and respects VECTOR_BACKEND config.
    """

    @staticmethod
    def get_embedding_engine() -> EmbeddingEngine:
        return get_embedding_engine()

    @staticmethod
    def set_embedding_engine(engine: Optional[EmbeddingEngine]) -> None:
        set_embedding_engine(engine)

    @staticmethod
    def get_vector_index() -> VectorIndex:
        return get_vector_index(
            dim=settings.VECTOR_DIMENSION,
            threshold=settings.VECTOR_SIMILARITY_THRESHOLD,
        )

    @staticmethod
    def set_vector_index(index: Optional[VectorIndex]) -> None:
        set_vector_index(index)
        if index is not None:
            SemanticCacheFactory.set_vector_backend(index)

    @staticmethod
    def get_arbiter():
        from backend.guardrails.factory import get_guardrail_arbiter
        return get_guardrail_arbiter()

    @staticmethod
    def set_arbiter(arbiter) -> None:
        from backend.guardrails.factory import set_guardrail_arbiter
        set_guardrail_arbiter(arbiter)

    @staticmethod
    def get_volatility_engine():
        from backend.guardrails.factory import get_volatility_engine
        return get_volatility_engine()

    @staticmethod
    def set_volatility_engine(engine) -> None:
        from backend.guardrails.factory import set_volatility_engine
        set_volatility_engine(engine)

    @staticmethod
    def get_vector_backend() -> SemanticCacheBackend:
        """
        Authoritatively resolves the configured L2 vector backend.

        In production, missing dependencies for configured pgvector or qdrant
        will fail-closed by raising a RuntimeError.
        """
        global _cached_vector_backend, _cached_backend_type
        backend_type = (settings.VECTOR_BACKEND or "memory").lower()
        if _cached_vector_backend is not None and _cached_backend_type == backend_type:
            return _cached_vector_backend

        if backend_type == "pgvector":
            if PgVectorSemanticBackend is None:
                if settings.ENVIRONMENT == "production":
                    raise RuntimeError("Configured VECTOR_BACKEND='pgvector' is unavailable in production")
                logger.warning("PgVectorSemanticBackend unavailable; falling back to in-memory VectorIndex")
                _cached_vector_backend = get_vector_index(
                    dim=settings.VECTOR_DIMENSION,
                    threshold=settings.VECTOR_SIMILARITY_THRESHOLD,
                )
            else:
                _cached_vector_backend = PgVectorSemanticBackend(
                    default_threshold=settings.VECTOR_SIMILARITY_THRESHOLD,
                )
        elif backend_type == "qdrant":
            if QdrantSemanticBackend is None:
                if settings.ENVIRONMENT == "production":
                    raise RuntimeError("Configured VECTOR_BACKEND='qdrant' is unavailable in production")
                logger.warning("QdrantSemanticBackend unavailable; falling back to in-memory VectorIndex")
                _cached_vector_backend = get_vector_index(
                    dim=settings.VECTOR_DIMENSION,
                    threshold=settings.VECTOR_SIMILARITY_THRESHOLD,
                )
            else:
                _cached_vector_backend = QdrantSemanticBackend(
                    default_threshold=settings.VECTOR_SIMILARITY_THRESHOLD,
                    dimension=settings.VECTOR_DIMENSION,
                )
        else:
            _cached_vector_backend = get_vector_index(
                dim=settings.VECTOR_DIMENSION,
                threshold=settings.VECTOR_SIMILARITY_THRESHOLD,
            )

        _cached_backend_type = backend_type
        return _cached_vector_backend

    @staticmethod
    def set_vector_backend(backend: Optional[SemanticCacheBackend]) -> None:
        global _cached_vector_backend, _cached_backend_type
        _cached_vector_backend = backend
        _cached_backend_type = (settings.VECTOR_BACKEND or "memory").lower() if backend is not None else None

    @staticmethod
    def get_semantic_cache_service() -> "SemanticCacheService":
        global _cached_semantic_service
        if _cached_semantic_service is None:
            _cached_semantic_service = SemanticCacheService()
        return _cached_semantic_service

    @staticmethod
    def set_semantic_cache_service(service: Optional["SemanticCacheService"]) -> None:
        global _cached_semantic_service
        _cached_semantic_service = service
        if service is not None:
            if service.embedding_engine:
                SemanticCacheFactory.set_embedding_engine(service.embedding_engine)
            if service.backend:
                SemanticCacheFactory.set_vector_backend(service.backend)
            if service.arbiter:
                SemanticCacheFactory.set_arbiter(service.arbiter)
            if service.volatility_engine:
                SemanticCacheFactory.set_volatility_engine(service.volatility_engine)

    @staticmethod
    def reset_singletons() -> None:
        global _cached_vector_backend, _cached_backend_type, _cached_semantic_service
        _cached_vector_backend = None
        _cached_backend_type = None
        _cached_semantic_service = None
        set_embedding_engine(None)
        set_vector_index(None)
        from backend.guardrails.factory import set_guardrail_arbiter, set_volatility_engine
        set_guardrail_arbiter(None)
        set_volatility_engine(None)


class SemanticCacheService(SemanticCacheBackend):
    """
    Main orchestration service for L2 semantic cache operations.

    Combines embedding generation, vector search (via configured SemanticCacheBackend),
    guardrail safety evaluation, and volatility-based TTL assignment into a cohesive service.
    """

    def __init__(
        self,
        embedding_engine: Optional[EmbeddingEngine] = None,
        backend: Optional[SemanticCacheBackend] = None,
        arbiter=None,
        volatility_engine=None,
        default_similarity_threshold: Optional[float] = None,
        vector_index: Optional[SemanticCacheBackend] = None,
    ) -> None:
        self._embedding_engine = embedding_engine
        self._backend = backend or vector_index
        self._arbiter = arbiter
        self._volatility_engine = volatility_engine
        self.default_similarity_threshold = (
            default_similarity_threshold
            if default_similarity_threshold is not None
            else settings.VECTOR_SIMILARITY_THRESHOLD
        )

    @property
    def embedding_engine(self) -> EmbeddingEngine:
        return self._embedding_engine or SemanticCacheFactory.get_embedding_engine()

    @embedding_engine.setter
    def embedding_engine(self, val: Optional[EmbeddingEngine]) -> None:
        self._embedding_engine = val

    @property
    def backend(self) -> SemanticCacheBackend:
        return self._backend or SemanticCacheFactory.get_vector_backend()

    @backend.setter
    def backend(self, val: Optional[SemanticCacheBackend]) -> None:
        self._backend = val

    @property
    def vector_index(self) -> SemanticCacheBackend:
        """Backwards compatibility alias for self.backend."""
        return self.backend

    @vector_index.setter
    def vector_index(self, val: SemanticCacheBackend) -> None:
        self.backend = val

    @property
    def arbiter(self):
        return self._arbiter or SemanticCacheFactory.get_arbiter()

    @arbiter.setter
    def arbiter(self, val) -> None:
        self._arbiter = val

    @property
    def volatility_engine(self):
        return self._volatility_engine or SemanticCacheFactory.get_volatility_engine()

    @volatility_engine.setter
    def volatility_engine(self, val) -> None:
        self._volatility_engine = val

    async def insert(
        self,
        scope_hash: str,
        exact_request_hash: str,
        vector: List[float],
        response_payload: dict,
        created_at: float,
        input_text: str = "",
        system_prompt: Optional[str] = None,
        provider: str = "unknown",
        model: str = "unknown",
        ttl_seconds: Optional[int] = None,
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """
        Stores a vector entry under scope_hash partition with volatility-based TTL.
        """
        if ttl_seconds is None and self.volatility_engine:
            try:
                volatility_classification = await self.volatility_engine.classify(input_text)
                ttl_seconds = volatility_classification.ttl_seconds
            except Exception as e:
                logger.warning(f"Volatility classification failed; using default TTL: {e}")
                ttl_seconds = settings.DEFAULT_CACHE_TTL_SECONDS

        await self.backend.insert(
            scope_hash=scope_hash,
            exact_request_hash=exact_request_hash,
            vector=vector,
            response_payload=response_payload,
            created_at=created_at,
            input_text=input_text,
            system_prompt=system_prompt,
            provider=provider,
            model=model,
            ttl_seconds=ttl_seconds,
            tenant_id=tenant_id,
            project_id=project_id,
            namespace=namespace,
            tags=tags,
        )

    async def search(
        self,
        query_vector: List[float],
        scope_hash: str,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None,
    ) -> List[SemanticCandidate]:
        """
        Search for semantic cache candidates within a scope using the configured backend.
        """
        threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else self.default_similarity_threshold
        )
        return await self.backend.search(
            query_vector=query_vector,
            scope_hash=scope_hash,
            top_k=top_k,
            similarity_threshold=threshold,
        )

    async def delete(self, exact_request_hash: str) -> bool:
        """Deletes entry by exact_request_hash from backend."""
        return await self.backend.delete(exact_request_hash)

    async def delete_by_scope(self, scope_hash: str) -> int:
        """Deletes all entries matching scope_hash from backend."""
        return await self.backend.delete_by_scope(scope_hash)

    async def delete_by_project(self, tenant_id: str, project_id: str) -> int:
        """Deletes all vector entries belonging to a specific project within a tenant."""
        return await self.backend.delete_by_project(tenant_id, project_id)

    async def delete_by_scope_filters(
        self,
        tenant_id: str,
        project_id: Optional[str] = None,
        model: Optional[str] = None,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> int:
        """Deletes vector entries matching specific tenant, project, and scope filters."""
        return await self.backend.delete_by_scope_filters(
            tenant_id=tenant_id,
            project_id=project_id,
            model=model,
            namespace=namespace,
            tags=tags,
        )

    async def delete_by_tenant(self, tenant_id: str) -> int:
        """Deletes all entries matching tenant_id from backend."""
        return await self.backend.delete_by_tenant(tenant_id)

    async def inspect_key(self, exact_request_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieves detailed inspection information for a cached key."""
        return await self.backend.inspect_key(exact_request_hash)

    async def get_stats(self) -> Dict[str, Any]:
        """Returns statistics from backend."""
        return await self.backend.get_stats()

    async def ping(self) -> bool:
        """Health check - verifies all components are responsive."""
        try:
            # Test embedding engine
            if self.embedding_engine:
                await self.embedding_engine.embed("test")

            # Test vector backend
            if self.backend:
                backend_healthy = await self.backend.ping()
                if not backend_healthy:
                    return False

            # Test arbiter
            if self.arbiter:
                await self.arbiter.evaluate("test", "test")

            # Test volatility engine
            if self.volatility_engine:
                await self.volatility_engine.classify("test")

            return True
        except Exception as e:
            logger.warning(f"SemanticCacheService ping failed: {e}")
            return False

    async def clear(self) -> None:
        """Clears all entries (test isolation)."""
        await self.backend.clear()


def get_semantic_cache_service() -> SemanticCacheService:
    """Returns singleton SemanticCacheService instance."""
    return SemanticCacheFactory.get_semantic_cache_service()


def set_semantic_cache_service(service: Optional[SemanticCacheService]) -> None:
    """Explicitly sets or overrides semantic cache service (for tests)."""
    SemanticCacheFactory.set_semantic_cache_service(service)


__all__ = [
    "SemanticCacheFactory",
    "SemanticCacheService",
    "get_semantic_cache_service",
    "set_semantic_cache_service",
]
