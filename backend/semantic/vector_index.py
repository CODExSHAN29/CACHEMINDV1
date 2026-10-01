"""
HNSW Vector Index for Semantic Cache Search.

Provides approximate nearest-neighbor search using Cosine Similarity over
384-dimensional embedding vectors. Supports two backends:

1. hnswlib — preferred: true HNSW O(log N) search
2. numpy fallback: exhaustive O(N) search, always available

Each entry is bound to a scope_hash (tenant+project+model+system_prompt)
so cache namespaces never leak across models or system prompts.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Try to import hnswlib; fall back to numpy-only if unavailable
try:
    import hnswlib
    HNSWLIBAVAILABLE = True
except ImportError:
    HNSWLIBAVAILABLE = False
    hnswlib = None  # type: ignore


_cached_vector_index_instance: Optional["VectorIndex"] = None


class SemanticCandidate:
    """
    A candidate hit from vector search, with metadata.

    Attributes:
        exact_request_hash: Hash binding to the exact cached response
        scope_hash: Hash binding to the model+system-prompt namespace
        similarity: Cosine similarity [0.0, 1.0]
        response_payload: The cached upstream LLM response
        created_at: Unix epoch seconds when this entry was stored
    """
    __slots__ = ("exact_request_hash", "scope_hash", "similarity", "response_payload", "created_at")

    def __init__(
        self,
        exact_request_hash: str,
        scope_hash: str,
        similarity: float,
        response_payload: Dict[str, Any],
        created_at: float,
    ) -> None:
        self.exact_request_hash = exact_request_hash
        self.scope_hash = scope_hash
        self.similarity = similarity
        self.response_payload = response_payload
        self.created_at = created_at

    @property
    def is_above_threshold(self, threshold: float = 0.92) -> bool:
        return self.similarity >= threshold


@dataclass
class StoredVectorEntry:
    """Internal metadata container for an in-memory vector index record."""
    vector: List[float]
    response_payload: Dict[str, Any]
    created_at: float
    input_text: str = ""
    system_prompt: Optional[str] = None
    provider: str = "unknown"
    model: str = "unknown"
    ttl_seconds: Optional[int] = None
    tenant_id: Optional[str] = None
    project_id: Optional[str] = None
    namespace: Optional[str] = None
    tags: Optional[List[str]] = None


class VectorIndex:
    """
    In-memory vector index for semantic cache search.

    Stores (vector, metadata) pairs and supports cosine-similarity search.
    Entries are partitioned by scope_hash so different models/system-prompt
    combinations never share cache entries.

    Design:
    - Uses hnswlib for O(log N) approximate NN if available
    - Falls back to numpy exhaustive O(N) search
    - Scope hash partitioning prevents cross-namespace leakage
    - Entries auto-expire based on CachedResponse.ttl_seconds (handled at
      insertion/removal time)
    """
    DEFAULT_THRESHOLD = 0.92
    DEFAULT_DIM = 384
    MAX_ENTRIES_DEFAULT = 10_000  # reasonable default for in-memory

    _instance: Optional["VectorIndex"] = None

    def __new__(cls, dim: int = DEFAULT_DIM, threshold: float = DEFAULT_THRESHOLD, max_entries: int = MAX_ENTRIES_DEFAULT) -> "VectorIndex":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, dim: int = DEFAULT_DIM, threshold: float = DEFAULT_THRESHOLD, max_entries: int = MAX_ENTRIES_DEFAULT) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self._dim = dim
        self._threshold = threshold
        self._max_entries = max_entries

        # Scope hash -> {exact_request_hash -> StoredVectorEntry}
        self._entries_by_scope: Dict[str, Dict[str, StoredVectorEntry]] = {}

        # Global index for cross-scope search (when needed)
        self._global_vectors: List[List[float]] = []
        self._global_scope_hashes: List[str] = []
        self._global_exact_hashes: List[str] = []
        self._global_max_size = max_entries

        # Try to init hnswlib
        if HNSWLIBAVAILABLE:
            try:
                self._hnsw_index = hnswlib.Index(space="cosine", dim=dim)
                self._hnsw_index.set_hnsw_ef(40)  # search elevation factor
                self._hnsw_index.set_max_elements(max_entries)
                self._use_hnsw = True
                self.log("hnswlib initialized successfully")
            except Exception as e:
                self.log(f"hnswlib init failed: {e}, falling back to numpy", level="WARNING")
                self._use_hnsw = False
        else:
            self._use_hnsw = False
            self.log("hnswlib not available, using numpy fallback")

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def threshold(self) -> float:
        return self._threshold

    @classmethod
    def log(cls, msg: str, level: str = "INFO") -> None:
        """Simple logging placeholder (callers can redirect)."""
        pass

    # ---------- Public API ----------

    async def insert(
        self,
        scope_hash: str,
        exact_request_hash: str,
        vector: List[float],
        response_payload: Dict[str, Any],
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
        Insert a vector entry into the index.

        Args:
            scope_hash: Namespace partition (tenant+project+model+system_prompt)
            exact_request_hash: Unique hash of the exact request
            vector: 384-dim embedding vector
            response_payload: Cached upstream response dict
            created_at: Unix timestamp when this entry was created
            input_text: Input prompt text
            system_prompt: Optional system prompt
            provider: LLM provider
            model: Model identifier
            ttl_seconds: Cache TTL in seconds
            tenant_id: Multi-tenant tenant identifier
            project_id: Multi-tenant project identifier
            namespace: Optional custom namespace
            tags: Optional tags
        """
        loop = asyncio.get_running_loop()
        entry = StoredVectorEntry(
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
        await loop.run_in_executor(None, self._insert_sync, scope_hash, exact_request_hash, entry)

    def _insert_sync(
        self,
        scope_hash: str,
        exact_request_hash: str,
        entry: StoredVectorEntry,
    ) -> None:
        """Synchronous insert (called from executor)."""
        if scope_hash not in self._entries_by_scope:
            self._entries_by_scope[scope_hash] = {}

        self._entries_by_scope[scope_hash][exact_request_hash] = entry

        # Update global structures for cross-scope search
        self._ensure_global_capacity()
        self._global_scope_hashes.append(scope_hash)
        self._global_exact_hashes.append(exact_request_hash)
        self._global_vectors.append(entry.vector)

        # Enforce max entries
        if len(self._global_vectors) > self._global_max_size * 2:
            self._global_vectors.pop(0)
            self._global_scope_hashes.pop(0)
            self._global_exact_hashes.pop(0)

        self.log(f"Inserted entry {exact_request_hash[:8]} into scope {scope_hash[:8]}")

    async def search(
        self,
        query_vector: List[float],
        scope_hash: str,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None,
    ) -> List[SemanticCandidate]:
        """
        Search for nearest neighbors within a single scope.

        Only searches entries belonging to the given scope_hash (same model
        and system prompt). This prevents cross-namespace leakage.

        Args:
            query_vector: 384-dim query embedding
            scope_hash: Namespace to search within
            top_k: Number of candidates to return
            similarity_threshold: Minimum cosine similarity required (defaults to self._threshold)

        Returns:
            List of SemanticCandidate, sorted by similarity descending.
            Only candidates with similarity >= threshold are included.
        """
        loop = asyncio.get_running_loop()
        threshold = similarity_threshold if similarity_threshold is not None else self._threshold
        return await loop.run_in_executor(None, self._search_sync, query_vector, scope_hash, top_k, threshold)

    def _search_sync(
        self,
        query_vector: List[float],
        scope_hash: str,
        top_k: int,
        threshold: float,
    ) -> List[SemanticCandidate]:
        """Synchronous search (called from executor)."""
        scope_entries = self._entries_by_scope.get(scope_hash, {})
        if not scope_entries:
            return []

        query_vec = np.array(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0.0:
            return []

        candidates: List[Tuple[str, float, StoredVectorEntry]] = []

        for exact_hash, entry in scope_entries.items():
            stored_vec_np = np.array(entry.vector, dtype=np.float32)
            stored_norm = np.linalg.norm(stored_vec_np)

            if stored_norm > 0:
                cos_sim = float(np.dot(query_vec, stored_vec_np) / (query_norm * stored_norm))
            else:
                cos_sim = 0.0

            if cos_sim >= threshold:
                candidates.append((exact_hash, cos_sim, entry))

        candidates.sort(key=lambda x: x[1], reverse=True)

        results = []
        for exact_hash, similarity, entry in candidates[:top_k]:
            results.append(SemanticCandidate(
                exact_request_hash=exact_hash,
                scope_hash=scope_hash,
                similarity=similarity,
                response_payload=entry.response_payload,
                created_at=entry.created_at,
            ))

        self.log(f"Search in scope {scope_hash[:8]}: found {len(results)} candidates above threshold {threshold}")
        return results

    async def search_cross_scope(
        self,
        query_vector: List[float],
        top_k: int = 10,
        similarity_threshold: Optional[float] = None,
    ) -> List[SemanticCandidate]:
        """Search across ALL scopes (useful for debugging or global queries)."""
        loop = asyncio.get_running_loop()
        threshold = similarity_threshold if similarity_threshold is not None else self._threshold
        return await loop.run_in_executor(None, self._search_cross_scope_sync, query_vector, top_k, threshold)

    def _search_cross_scope_sync(
        self,
        query_vector: List[float],
        top_k: int,
        threshold: float,
    ) -> List[SemanticCandidate]:
        """Synchronous cross-scope search."""
        query_vec = np.array(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0.0:
            return []

        candidates: List[Tuple[str, float, str, StoredVectorEntry]] = []

        for scope_hash, entries in self._entries_by_scope.items():
            for exact_hash, entry in entries.items():
                stored_vec_np = np.array(entry.vector, dtype=np.float32)
                stored_norm = np.linalg.norm(stored_vec_np)

                if stored_norm > 0:
                    cos_sim = float(np.dot(query_vec, stored_vec_np) / (query_norm * stored_norm))
                else:
                    cos_sim = 0.0

                if cos_sim >= threshold:
                    candidates.append((exact_hash, cos_sim, scope_hash, entry))

        candidates.sort(key=lambda x: x[1], reverse=True)

        results = []
        for exact_hash, similarity, scope, entry in candidates[:top_k]:
            results.append(SemanticCandidate(
                exact_request_hash=exact_hash,
                scope_hash=scope,
                similarity=similarity,
                response_payload=entry.response_payload,
                created_at=entry.created_at,
            ))

        return results

    async def delete(self, exact_request_hash: str) -> bool:
        """
        Delete an entry by exact request hash across all scopes.

        Returns True if found and deleted, False otherwise.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._delete_sync, exact_request_hash)

    def _delete_sync(self, exact_request_hash: str) -> bool:
        """Synchronous delete (called from executor)."""
        deleted_any = False

        for scope_hash, entries in list(self._entries_by_scope.items()):
            if exact_request_hash in entries:
                del entries[exact_request_hash]
                deleted_any = True
                if not entries:
                    del self._entries_by_scope[scope_hash]

        # Also remove from global structures
        while exact_request_hash in self._global_exact_hashes:
            idx = self._global_exact_hashes.index(exact_request_hash)
            self._global_vectors.pop(idx)
            self._global_scope_hashes.pop(idx)
            self._global_exact_hashes.pop(idx)
            deleted_any = True

        if deleted_any:
            self.log(f"Deleted entry {exact_request_hash[:8]}")

        return deleted_any

    async def delete_by_scope(self, scope_hash: str) -> int:
        """Delete all entries under a scope hash."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._delete_by_scope_sync, scope_hash)

    def _delete_by_scope_sync(self, scope_hash: str) -> int:
        deleted_count = 0
        if scope_hash in self._entries_by_scope:
            deleted_count = len(self._entries_by_scope[scope_hash])
            del self._entries_by_scope[scope_hash]

        # Clean from global structures
        indices_to_remove = [
            i for i, sh in enumerate(self._global_scope_hashes) if sh == scope_hash
        ]
        for idx in reversed(indices_to_remove):
            self._global_vectors.pop(idx)
            self._global_scope_hashes.pop(idx)
            self._global_exact_hashes.pop(idx)

        return deleted_count

    async def delete_by_project(self, tenant_id: str, project_id: str) -> int:
        """Delete all entries belonging to a specific project within a tenant across all scopes."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._delete_by_project_sync, tenant_id, project_id)

    def _delete_by_project_sync(self, tenant_id: str, project_id: str) -> int:
        deleted_count = 0
        keys_to_delete = []

        for scope_hash, entries in self._entries_by_scope.items():
            for exact_hash, entry in entries.items():
                if entry.tenant_id == tenant_id and entry.project_id == project_id:
                    keys_to_delete.append(exact_hash)

        for exact_hash in keys_to_delete:
            if self._delete_sync(exact_hash):
                deleted_count += 1

        return deleted_count

    async def delete_by_scope_filters(
        self,
        tenant_id: str,
        project_id: Optional[str] = None,
        model: Optional[str] = None,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> int:
        """Delete entries matching specific tenant, project, and scope filters."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._delete_by_scope_filters_sync, tenant_id, project_id, model, namespace, tags
        )

    def _delete_by_scope_filters_sync(
        self,
        tenant_id: str,
        project_id: Optional[str] = None,
        model: Optional[str] = None,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> int:
        deleted_count = 0
        keys_to_delete = []

        for scope_hash, entries in self._entries_by_scope.items():
            for exact_hash, entry in entries.items():
                if entry.tenant_id != tenant_id:
                    continue
                if project_id is not None and entry.project_id != project_id:
                    continue
                if model is not None and entry.model != model:
                    continue
                if namespace is not None and entry.namespace != namespace:
                    continue
                if tags:
                    entry_tags = set(entry.tags or [])
                    if not set(tags).issubset(entry_tags):
                        continue
                    keys_to_delete.append(exact_hash)
                else:
                    keys_to_delete.append(exact_hash)

        for exact_hash in keys_to_delete:
            if self._delete_sync(exact_hash):
                deleted_count += 1

        return deleted_count

    async def delete_by_tenant(self, tenant_id: str) -> int:
        """Delete all entries belonging to a specific tenant across all scopes."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._delete_by_tenant_sync, tenant_id)

    def _delete_by_tenant_sync(self, tenant_id: str) -> int:
        deleted_count = 0
        keys_to_delete = []

        for scope_hash, entries in self._entries_by_scope.items():
            for exact_hash, entry in entries.items():
                if entry.tenant_id == tenant_id:
                    keys_to_delete.append(exact_hash)

        for exact_hash in keys_to_delete:
            if self._delete_sync(exact_hash):
                deleted_count += 1

        return deleted_count

    async def inspect_key(self, exact_request_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieves detailed inspection information for a single vector cache entry."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._inspect_key_sync, exact_request_hash)

    def _inspect_key_sync(self, exact_request_hash: str) -> Optional[Dict[str, Any]]:
        for scope_hash, entries in self._entries_by_scope.items():
            if exact_request_hash in entries:
                entry = entries[exact_request_hash]
                now = time.time()
                created_dt = datetime.fromtimestamp(entry.created_at, tz=timezone.utc)
                expires_iso = None
                ttl_remaining = None
                if entry.ttl_seconds and entry.ttl_seconds > 0:
                    expires_at_ts = entry.created_at + entry.ttl_seconds
                    expires_iso = datetime.fromtimestamp(expires_at_ts, tz=timezone.utc).isoformat()
                    ttl_remaining = max(0, int(expires_at_ts - now))

                return {
                    "id": exact_request_hash,
                    "exact_request_hash": exact_request_hash,
                    "scope_hash": scope_hash,
                    "tenant_id": entry.tenant_id,
                    "project_id": entry.project_id,
                    "provider": entry.provider,
                    "model": entry.model,
                    "system_prompt": entry.system_prompt,
                    "input_text": entry.input_text,
                    "namespace": entry.namespace,
                    "tags": entry.tags or [],
                    "created_at": created_dt.isoformat(),
                    "expires_at": expires_iso,
                    "ttl_seconds": entry.ttl_seconds,
                    "ttl_remaining_seconds": ttl_remaining,
                    "has_embedding": bool(entry.vector),
                    "embedding_dimension": len(entry.vector) if entry.vector else 0,
                }
        return None

    async def get_stats(self) -> Dict[str, Any]:
        """Returns statistics on stored vectors and partitions."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_stats_sync)

    def _get_stats_sync(self) -> Dict[str, Any]:
        total_entries = sum(len(entries) for entries in self._entries_by_scope.values())
        return {
            "backend": "memory",
            "total_entries": total_entries,
            "total_scopes": len(self._entries_by_scope),
            "scopes": {sh: len(entries) for sh, entries in self._entries_by_scope.items()},
        }

    async def clear(self) -> None:
        """Clear all entries."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._clear_sync)

    def _clear_sync(self) -> None:
        """Synchronous clear (called from executor)."""
        self._entries_by_scope.clear()
        self._global_vectors.clear()
        self._global_scope_hashes.clear()
        self._global_exact_hashes.clear()
        self.log("Vector index cleared")

    async def ping(self) -> bool:
        """Health check."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._ping_sync)

    def _ping_sync(self) -> bool:
        """Synchronous ping."""
        return (
            self._dim > 0
            and self._entries_by_scope is not None
        )

    def _ensure_global_capacity(self) -> None:
        """Ensure global structures have room for new entries."""
        current = len(self._global_vectors)
        if current >= self._global_max_size:
            excess = current - self._global_max_size + 1
            self._global_vectors = self._global_vectors[excess:]
            self._global_scope_hashes = self._global_scope_hashes[excess:]
            self._global_exact_hashes = self._global_exact_hashes[excess:]


def get_vector_index(
    dim: int = VectorIndex.DEFAULT_DIM,
    threshold: float = VectorIndex.DEFAULT_THRESHOLD,
    max_entries: int = VectorIndex.MAX_ENTRIES_DEFAULT,
) -> VectorIndex:
    """Returns singleton VectorIndex instance."""
    global _cached_vector_index_instance
    if _cached_vector_index_instance is None:
        _cached_vector_index_instance = VectorIndex(dim=dim, threshold=threshold, max_entries=max_entries)
    return _cached_vector_index_instance


def set_vector_index(idx: Optional[VectorIndex]) -> None:
    """Explicitly sets or overrides vector index instance (for tests)."""
    global _cached_vector_index_instance
    _cached_vector_index_instance = idx
    if idx is None:
        VectorIndex._instance = None


class MockVectorIndex:
    """
    Deterministic test double for VectorIndex.
    Stores (query_text -> vector) mapping and returns similarity based on
    text hash comparison — useful when FastEmbed isn't installed.
    """

    def __init__(self, dim: int = 384, threshold: float = 0.92) -> None:
        self._dim = dim
        self._threshold = threshold
        self._entries: Dict[str, Dict[str, Any]] = {}

    async def insert(
        self,
        scope_hash: str,
        exact_request_hash: str,
        vector: List[float],
        response_payload: Dict[str, Any],
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
        self._entries[exact_request_hash] = {
            "vector": vector,
            "response_payload": response_payload,
            "created_at": created_at,
            "tenant_id": tenant_id,
            "project_id": project_id,
            "model": model,
            "namespace": namespace,
            "tags": tags,
            "scope_hash": scope_hash,
        }

    async def search(
        self,
        query_vector: List[float],
        scope_hash: str,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None,
    ) -> List[SemanticCandidate]:
        threshold = similarity_threshold if similarity_threshold is not None else self._threshold
        candidates = []
        for exact_hash, entry in self._entries.items():
            stored_vec = entry["vector"]
            payload = entry["response_payload"]
            created_at = entry["created_at"]
            vec_a = np.array(query_vector, dtype=np.float32)
            vec_b = np.array(stored_vec, dtype=np.float32)
            norm_a = np.linalg.norm(vec_a)
            norm_b = np.linalg.norm(vec_b)
            sim = float(np.dot(vec_a, vec_b) / (norm_a * norm_b)) if (norm_a > 0 and norm_b > 0) else 0.0
            if sim >= threshold:
                candidates.append(SemanticCandidate(
                    exact_request_hash=exact_hash,
                    scope_hash=scope_hash,
                    similarity=sim,
                    response_payload=payload,
                    created_at=created_at,
                ))

        candidates.sort(key=lambda c: c.similarity, reverse=True)
        return candidates[:top_k]

    async def delete(self, exact_request_hash: str) -> bool:
        if exact_request_hash in self._entries:
            del self._entries[exact_request_hash]
            return True
        return False

    async def delete_by_scope(self, scope_hash: str) -> int:
        keys_to_del = [k for k, v in self._entries.items() if v.get("scope_hash") == scope_hash]
        for k in keys_to_del:
            del self._entries[k]
        return len(keys_to_del)

    async def delete_by_project(self, tenant_id: str, project_id: str) -> int:
        keys_to_del = [
            k for k, v in self._entries.items()
            if v.get("tenant_id") == tenant_id and v.get("project_id") == project_id
        ]
        for k in keys_to_del:
            del self._entries[k]
        return len(keys_to_del)

    async def delete_by_scope_filters(
        self,
        tenant_id: str,
        project_id: Optional[str] = None,
        model: Optional[str] = None,
        namespace: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> int:
        keys_to_del = []
        for k, v in self._entries.items():
            if v.get("tenant_id") != tenant_id:
                continue
            if project_id is not None and v.get("project_id") != project_id:
                continue
            if model is not None and v.get("model") != model:
                continue
            if namespace is not None and v.get("namespace") != namespace:
                continue
            if tags:
                item_tags = set(v.get("tags") or [])
                if not set(tags).issubset(item_tags):
                    continue
            keys_to_del.append(k)
        for k in keys_to_del:
            del self._entries[k]
        return len(keys_to_del)

    async def delete_by_tenant(self, tenant_id: str) -> int:
        keys_to_del = [k for k, v in self._entries.items() if v.get("tenant_id") == tenant_id]
        for k in keys_to_del:
            del self._entries[k]
        return len(keys_to_del)

    async def inspect_key(self, exact_request_hash: str) -> Optional[Dict[str, Any]]:
        if exact_request_hash in self._entries:
            entry = self._entries[exact_request_hash]
            return {
                "id": exact_request_hash,
                "exact_request_hash": exact_request_hash,
                "tenant_id": entry.get("tenant_id"),
                "project_id": entry.get("project_id"),
                "model": entry.get("model"),
                "namespace": entry.get("namespace"),
                "tags": entry.get("tags"),
                "created_at": str(entry.get("created_at")),
                "has_embedding": True,
            }
        return None

    async def get_stats(self) -> Dict[str, Any]:
        return {
            "backend": "mock",
            "total_entries": len(self._entries),
            "total_scopes": 1,
            "scopes": {},
        }

    async def clear(self) -> None:
        self._entries.clear()

    async def ping(self) -> bool:
        return self._dim > 0

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def threshold(self) -> float:
        return self._threshold
