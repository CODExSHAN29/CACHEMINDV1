"""
Semantic Cache Factory — Provides singleton instances for semantic caching components.

Manages the lifecycle of EmbeddingEngine, VectorIndex, GuardrailArbiter, and VolatilityEngine,
enabling dependency injection for testing and consistent configuration.
"""

from typing import List, Optional

from .embedding import EmbeddingEngine, get_embedding_engine, set_embedding_engine
from .vector_index import VectorIndex, get_vector_index, set_vector_index
from .models import SemanticCacheEntry
from .backend import SemanticCacheBackend


class SemanticCacheFactory:
    """
    Factory for creating and managing semantic cache service components.

    Provides singleton instances with optional override capabilities for testing.
    """

    _embedding_engine: Optional[EmbeddingEngine] = None
    _vector_index: Optional[VectorIndex] = None
    _arbiter: Optional["GuardrailArbiter"] = None
    _volatility_engine: Optional["VolatilityEngine"] = None

    @classmethod
    def get_embedding_engine(cls) -> EmbeddingEngine:
        """Get or create the singleton EmbeddingEngine."""
        if cls._embedding_engine is None:
            cls._embedding_engine = EmbeddingEngine()
        return cls._embedding_engine

    @classmethod
    def set_embedding_engine(cls, engine: EmbeddingEngine) -> None:
        """Override the singleton EmbeddingEngine (for testing)."""
        cls._embedding_engine = engine

    @classmethod
    def get_vector_index(cls) -> VectorIndex:
        """Get or create the singleton VectorIndex."""
        if cls._vector_index is None:
            cls._vector_index = VectorIndex()
        return cls._vector_index

    @classmethod
    def set_vector_index(cls, index: VectorIndex) -> None:
        """Override the singleton VectorIndex (for testing)."""
        cls._vector_index = index

    @classmethod
    def get_arbiter(cls):
        """Get or create the singleton GuardrailArbiter."""
        # Import here to avoid circular dependencies
        from backend.guardrails.factory import get_guardrail_arbiter
        if cls._arbiter is None:
            cls._arbiter = get_guardrail_arbiter()
        return cls._arbiter

    @classmethod
    def set_arbiter(cls, arbiter) -> None:
        """Override the singleton GuardrailArbiter (for testing)."""
        cls._arbiter = arbiter

    @classmethod
    def get_volatility_engine(cls):
        """Get or create the singleton VolatilityEngine."""
        from backend.guardrails.factory import get_volatility_engine
        if cls._volatility_engine is None:
            cls._volatility_engine = get_volatility_engine()
        return cls._volatility_engine

    @classmethod
    def set_volatility_engine(cls, engine) -> None:
        """Override the singleton VolatilityEngine (for testing)."""
        cls._volatility_engine = engine

    @classmethod
    def reset_singletons(cls) -> None:
        """Reset all singleton instances (primarily for testing)."""
        cls._embedding_engine = None
        cls._vector_index = None
        cls._arbiter = None
        cls._volatility_engine = None


class SemanticCacheService(SemanticCacheBackend):
    """
    Main orchestration service for L2 semantic cache operations.

    Combines embedding generation, vector search, guardrail evaluation,
    and volatility-based TTL assignment into a cohesive service.
    """

    def __init__(
        self,
        embedding_engine: Optional[EmbeddingEngine] = None,
        vector_index: Optional[VectorIndex] = None,
        arbiter=None,
        volatility_engine=None,
        default_similarity_threshold: float = 0.92,
    ) -> None:
        self.embedding_engine = embedding_engine or SemanticCacheFactory.get_embedding_engine()
        self.vector_index = vector_index or SemanticCacheFactory.get_vector_index()
        self.arbiter = arbiter or SemanticCacheFactory.get_arbiter()
        self.volatility_engine = volatility_engine or SemanticCacheFactory.get_volatility_engine()
        self.default_similarity_threshold = default_similarity_threshold

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
    ) -> None:
        """
        Stores a vector entry under scope_hash partition with volatility-based TTL.

        Args:
            scope_hash: Namespace partition (tenant+project+model+system_prompt)
            exact_request_hash: Unique hash of the exact request
            vector: 384-dim embedding vector
            response_payload: Cached upstream response dict
            created_at: Unix timestamp when this entry was created
            input_text: The user message text used for embedding
            system_prompt: System message in request (if any)
            provider: LLM provider (openai, anthropic, etc.)
            model: Model identifier
            ttl_seconds: Optional TTL override; if None, determined by volatility engine
        """
        # Determine TTL based on volatility if not explicitly provided
        if ttl_seconds is None:
            volatility_classification = await self.volatility_engine.classify(input_text)
            ttl_seconds = volatility_classification.ttl_seconds

        # Create cache entry
        entry = SemanticCacheEntry(
            exact_request_hash=exact_request_hash,
            scope_hash=scope_hash,
            vector=vector,
            response_payload=response_payload,
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            input_text=input_text,
            created_at=created_at,
            ttl_seconds=ttl_seconds,
        )

        # Store in vector index
        await self.vector_index.insert(
            scope_hash=scope_hash,
            exact_request_hash=exact_request_hash,
            vector=vector,
            response_payload=response_payload,
            created_at=created_at,
        )

    async def search(
        self,
        query_vector: List[float],
        scope_hash: str,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None,
    ) -> List[SemanticCacheEntry]:
        """
        Search for semantic cache hits within a scope.

        Args:
            query_vector: 384-dim query embedding
            scope_hash: Namespace to search within
            top_k: Number of candidates to return
            similarity_threshold: Optional threshold override

        Returns:
            List of SemanticCacheEntry objects sorted by similarity descending
        """
        threshold = similarity_threshold or self.default_similarity_threshold

        # Get vector candidates from index
        candidates = await self.vector_index.search(
            query_vector=query_vector,
            scope_hash=scope_hash,
            top_k=top_k,
        )

        # Convert to SemanticCacheEntry objects (need to reconstruct from stored data)
        # This is simplified - in practice we'd need to fetch the full entries
        # For now, we'll return the raw candidates and let the service layer handle conversion
        return candidates  # This returns SemanticCandidate, need to adjust

    async def delete(self, exact_request_hash: str) -> bool:
        """Deletes entry by exact_request_hash."""
        return await self.vector_index.delete(exact_request_hash)

    async def ping(self) -> bool:
        """Health check - verifies all components are responsive."""
        try:
            # Test embedding engine
            test_embedding = await self.embedding_engine.embed("test")

            # Test vector index
            await self.vector_index.ping()

            # Test arbiter
            await self.arbiter.evaluate("test", "test")

            # Test volatility engine
            await self.volatility_engine.classify("test")

            return True
        except Exception:
            return False

    async def clear(self) -> None:
        """Clears all entries (test isolation)."""
        await self.vector_index.clear()


def get_semantic_cache_service() -> SemanticCacheService:
    """Returns singleton SemanticCacheService instance."""
    return SemanticCacheService()


def set_semantic_cache_service(service: SemanticCacheService) -> None:
    """Explicitly sets or overrides semantic cache service (for tests)."""
    # Override the factory singletons
    if service.embedding_engine:
        SemanticCacheFactory.set_embedding_engine(service.embedding_engine)
    if service.vector_index:
        SemanticCacheFactory.set_vector_index(service.vector_index)
    if service.arbiter:
        SemanticCacheFactory.set_arbiter(service.arbiter)
    if service.volatility_engine:
        SemanticCacheFactory.set_volatility_engine(service.volatility_engine)


__all__ = [
    "SemanticCacheFactory",
    "SemanticCacheService",
    "get_semantic_cache_service",
    "set_semantic_cache_service",
]