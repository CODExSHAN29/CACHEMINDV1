"""
PostgreSQL + pgvector Semantic Cache Backend.

Provides persistent, production-grade vector similarity search using
pgvector (HNSW / IVFFlat / Cosine distance) with multi-tenant namespace partitioning.
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Callable, Dict, List, Optional
import numpy as np
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.db.models import SemanticVectorEntry, utc_now
from backend.db.session import AsyncSessionLocal
from backend.semantic.backend import SemanticCacheBackend
from backend.semantic.vector_index import SemanticCandidate

logger = logging.getLogger("cachemind.semantic.pgvector")


class PgVectorSemanticBackend(SemanticCacheBackend):
    """
    Persistent L2 semantic cache backend powered by PostgreSQL & pgvector.

    Fully supports namespace partitioning, volatility-based TTL expiry,
    and cosine similarity ranking.
    """

    def __init__(
        self,
        session_factory: Optional[Callable[[], AsyncSession]] = None,
        default_threshold: float = 0.92,
    ) -> None:
        self._session_factory = session_factory
        self.default_threshold = default_threshold

    @property
    def session_factory(self) -> Any:
        if self._session_factory is not None:
            return self._session_factory
        import backend.db.session as session_mod
        return session_mod.AsyncSessionLocal

    @session_factory.setter
    def session_factory(self, val: Any) -> None:
        self._session_factory = val

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
        """Stores a vector entry in PostgreSQL under scope_hash partition."""
        ttl = ttl_seconds if ttl_seconds is not None else settings.DEFAULT_CACHE_TTL_SECONDS
        created_dt = datetime.fromtimestamp(created_at, tz=timezone.utc)
        expires_at = created_dt + timedelta(seconds=ttl) if ttl > 0 else None

        async with self.session_factory() as session:
            # Check if entry already exists (upsert pattern)
            existing = await session.execute(
                select(SemanticVectorEntry).where(
                    SemanticVectorEntry.exact_request_hash == exact_request_hash
                )
            )
            record = existing.scalar_one_or_none()

            if record:
                record.scope_hash = scope_hash
                record.vector = vector
                record.response_payload = response_payload
                record.input_text = input_text
                record.system_prompt = system_prompt
                record.provider = provider
                record.model = model
                record.ttl_seconds = ttl
                record.expires_at = expires_at
                record.tenant_id = tenant_id
                record.project_id = project_id
                record.namespace = namespace
                record.tags = tags
                record.created_at = created_dt
            else:
                record = SemanticVectorEntry(
                    scope_hash=scope_hash,
                    exact_request_hash=exact_request_hash,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    provider=provider,
                    model=model,
                    system_prompt=system_prompt,
                    input_text=input_text,
                    namespace=namespace,
                    tags=tags,
                    response_payload=response_payload,
                    embedding=vector,
                    created_at=created_dt,
                    ttl_seconds=ttl,
                    expires_at=expires_at,
                )
                session.add(record)

            await session.commit()
            logger.debug("Saved pgvector entry %s in scope %s", exact_request_hash[:8], scope_hash[:8])

    async def search(
        self,
        query_vector: List[float],
        scope_hash: str,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None,
    ) -> List[SemanticCandidate]:
        """
        Executes vector similarity search within scope_hash partition.
        Uses native pgvector cosine distance <=> on PostgreSQL,
        with in-memory numpy fallback for non-Postgres engines.
        """
        threshold = similarity_threshold if similarity_threshold is not None else self.default_threshold
        now = utc_now()

        async with self.session_factory() as session:
            bind = session.bind
            is_postgres = bind.dialect.name == "postgresql" if bind else False

            if is_postgres:
                # Native PostgreSQL pgvector cosine similarity
                similarity_expr = (1.0 - SemanticVectorEntry.embedding.cosine_distance(query_vector)).label("similarity")
                stmt = (
                    select(SemanticVectorEntry, similarity_expr)
                    .where(SemanticVectorEntry.scope_hash == scope_hash)
                    .where(
                        or_(
                            SemanticVectorEntry.expires_at.is_(None),
                            SemanticVectorEntry.expires_at > now,
                        )
                    )
                    .order_by(SemanticVectorEntry.embedding.cosine_distance(query_vector))
                    .limit(top_k * 2)
                )

                result = await session.execute(stmt)
                rows = result.all()

                candidates = []
                for entry, sim in rows:
                    sim_val = float(sim) if sim is not None else 0.0
                    if sim_val >= threshold:
                        c_at = 0.0
                        if entry.created_at:
                            c_dt = entry.created_at
                            if c_dt.tzinfo is None:
                                c_dt = c_dt.replace(tzinfo=timezone.utc)
                            c_at = c_dt.timestamp()
                        candidates.append(
                            SemanticCandidate(
                                exact_request_hash=entry.exact_request_hash,
                                scope_hash=entry.scope_hash,
                                similarity=sim_val,
                                response_payload=entry.response_payload,
                                created_at=c_at,
                            )
                        )
                    if len(candidates) >= top_k:
                        break

                return candidates

            else:
                # SQLite / non-Postgres fallback
                stmt = (
                    select(SemanticVectorEntry)
                    .where(SemanticVectorEntry.scope_hash == scope_hash)
                    .where(
                        or_(
                            SemanticVectorEntry.expires_at.is_(None),
                            SemanticVectorEntry.expires_at > now,
                        )
                    )
                )
                result = await session.execute(stmt)
                entries = result.scalars().all()

                if not entries:
                    return []

                query_vec = np.array(query_vector, dtype=np.float32)
                query_norm = np.linalg.norm(query_vec)

                scored: List[tuple[SemanticVectorEntry, float]] = []
                for entry in entries:
                    stored_vec = np.array(entry.embedding, dtype=np.float32)
                    stored_norm = np.linalg.norm(stored_vec)
                    if query_norm > 0 and stored_norm > 0:
                        sim = float(np.dot(query_vec, stored_vec) / (query_norm * stored_norm))
                    else:
                        sim = 0.0

                    if sim >= threshold:
                        scored.append((entry, sim))

                scored.sort(key=lambda x: x[1], reverse=True)

                results: List[SemanticCandidate] = []
                for e, sim in scored[:top_k]:
                    c_at = 0.0
                    if e.created_at:
                        c_dt = e.created_at
                        if c_dt.tzinfo is None:
                            c_dt = c_dt.replace(tzinfo=timezone.utc)
                        c_at = c_dt.timestamp()
                    results.append(
                        SemanticCandidate(
                            exact_request_hash=e.exact_request_hash,
                            scope_hash=e.scope_hash,
                            similarity=sim,
                            response_payload=e.response_payload,
                            created_at=c_at,
                        )
                    )
                return results

    async def delete(self, exact_request_hash: str) -> bool:
        """Deletes entry by exact_request_hash."""
        async with self.session_factory() as session:
            stmt = delete(SemanticVectorEntry).where(
                SemanticVectorEntry.exact_request_hash == exact_request_hash
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def delete_by_scope(self, scope_hash: str) -> int:
        """Deletes all entries under a scope partition."""
        async with self.session_factory() as session:
            stmt = delete(SemanticVectorEntry).where(
                SemanticVectorEntry.scope_hash == scope_hash
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def delete_by_tenant(self, tenant_id: str) -> int:
        """Deletes all entries belonging to a tenant."""
        async with self.session_factory() as session:
            stmt = delete(SemanticVectorEntry).where(
                SemanticVectorEntry.tenant_id == tenant_id
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def inspect_key(self, exact_request_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieves detailed inspection information for a single vector cache entry."""
        async with self.session_factory() as session:
            stmt = select(SemanticVectorEntry).where(
                SemanticVectorEntry.exact_request_hash == exact_request_hash
            )
            result = await session.execute(stmt)
            entry = result.scalar_one_or_none()
            if not entry:
                return None

            now = utc_now()
            ttl_remaining = None
            if entry.expires_at:
                exp = entry.expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                ttl_remaining = max(0, int((exp - now).total_seconds()))

            created_iso = None
            if entry.created_at:
                c_dt = entry.created_at
                if c_dt.tzinfo is None:
                    c_dt = c_dt.replace(tzinfo=timezone.utc)
                created_iso = c_dt.isoformat()

            exp_iso = None
            if entry.expires_at:
                e_dt = entry.expires_at
                if e_dt.tzinfo is None:
                    e_dt = e_dt.replace(tzinfo=timezone.utc)
                exp_iso = e_dt.isoformat()

            return {
                "id": entry.id,
                "exact_request_hash": entry.exact_request_hash,
                "scope_hash": entry.scope_hash,
                "tenant_id": entry.tenant_id,
                "project_id": entry.project_id,
                "provider": entry.provider,
                "model": entry.model,
                "system_prompt": entry.system_prompt,
                "input_text": entry.input_text,
                "namespace": entry.namespace,
                "tags": entry.tags,
                "created_at": created_iso,
                "expires_at": exp_iso,
                "ttl_seconds": entry.ttl_seconds,
                "ttl_remaining_seconds": ttl_remaining,
                "has_embedding": entry.embedding is not None,
                "embedding_dimension": len(entry.embedding) if entry.embedding is not None else 0,
            }

    async def get_stats(self) -> Dict[str, Any]:
        """Returns statistics on stored vectors and partitions."""
        async with self.session_factory() as session:
            total_res = await session.execute(select(func.count(SemanticVectorEntry.id)))
            total_entries = total_res.scalar() or 0

            scopes_res = await session.execute(
                select(SemanticVectorEntry.scope_hash, func.count(SemanticVectorEntry.id))
                .group_by(SemanticVectorEntry.scope_hash)
            )
            scope_counts = {row[0]: row[1] for row in scopes_res.all()}

            now = utc_now()
            active_res = await session.execute(
                select(func.count(SemanticVectorEntry.id)).where(
                    or_(
                        SemanticVectorEntry.expires_at.is_(None),
                        SemanticVectorEntry.expires_at > now,
                    )
                )
            )
            active_entries = active_res.scalar() or 0

            return {
                "backend": "pgvector",
                "total_entries": total_entries,
                "active_entries": active_entries,
                "total_scopes": len(scope_counts),
                "scopes": scope_counts,
            }

    async def ping(self) -> bool:
        """Health check verifying database connectivity."""
        try:
            async with self.session_factory() as session:
                res = await session.execute(text("SELECT 1"))
                return res.scalar() == 1
        except Exception as exc:
            logger.error("pgvector health check failed: %s", exc)
            return False

    async def clear(self) -> None:
        """Clears all vector cache entries (test isolation)."""
        async with self.session_factory() as session:
            await session.execute(delete(SemanticVectorEntry))
            await session.commit()
