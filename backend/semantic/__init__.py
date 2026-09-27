"""
Semantic Caching Package for CacheMind Phase 2.

Provides local ONNX embedding generation (FastEmbed), HNSW vector indexing,
and guardrail-protected semantic cache lookups.
"""

from backend.semantic.embedding import EmbeddingEngine, get_embedding_engine, set_embedding_engine
from backend.semantic.vector_index import VectorIndex, SemanticCandidate, get_vector_index, set_vector_index
from backend.semantic.models import (
    SemanticCacheEntry,
    SemanticCacheHitResult,
    SemanticScopeHash,
)
from backend.semantic.backend import SemanticCacheBackend
from backend.semantic.factory import get_semantic_cache_service, set_semantic_cache_service

__all__ = [
    # Embedding
    "EmbeddingEngine",
    "get_embedding_engine",
    "set_embedding_engine",
    # Vector Index
    "VectorIndex",
    "SemanticCandidate",
    "get_vector_index",
    "set_vector_index",
    # Models
    "SemanticCacheEntry",
    "SemanticCacheHitResult",
    "SemanticScopeHash",
    # Backend Protocol
    "SemanticCacheBackend",
    # Service
    "get_semantic_cache_service",
    "set_semantic_cache_service",
]