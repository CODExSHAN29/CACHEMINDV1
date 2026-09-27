"""
Data models for Semantic Caching in CacheMind Phase 2.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SemanticScopeHash(BaseModel):
    """Scope hash components binding a semantic cache namespace."""
    tenant_id: str
    project_id: str
    model: str
    system_prompt: Optional[str] = None
    namespace: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    def composite_key(self) -> str:
        """Returns deterministic string representation for hashing."""
        sp = self.system_prompt or ""
        ns = self.namespace or ""
        tags_str = ",".join(sorted(self.tags)) if self.tags else ""
        return f"t:{self.tenant_id}|p:{self.project_id}|m:{self.model}|ns:{ns}|tags:{tags_str}|sp:{sp}"


class SemanticCacheEntry(BaseModel):
    """
    Authoritative payload stored in the semantic vector index.

    Contains vector + metadata required for guardrail evaluation and telemetry.
    """
    exact_request_hash: str
    scope_hash: str
    vector: List[float]
    response_payload: Dict[str, Any]
    provider: str
    model: str
    system_prompt: Optional[str] = None
    input_text: str = Field(description="The user message text used for embedding")
    created_at: float
    ttl_seconds: int = 86400
    hit_count: int = 0
    namespace: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SemanticCacheHitResult(BaseModel):
    """
    Returned by the semantic cache service when a safe L2 hit is found.

    Includes similarity score and guardrail pass information.
    """
    exact_request_hash: str
    scope_hash: str
    similarity: float
    response_payload: Dict[str, Any]
    model: str
    cached_input_text: str
    guardrail_decision: str = "PASS"
    guardrail_checks_passed: List[str] = Field(default_factory=list)


class SemanticLookupTelemetry(BaseModel):
    """Telemetry data captured during a semantic lookup attempt."""
    embedding_latency_ms: float = 0.0
    vector_search_latency_ms: float = 0.0
    guardrail_latency_ms: float = 0.0
    total_semantic_lookup_ms: float = 0.0
    candidate_count: int = 0
    top_similarity: float = 0.0
    guardrail_status: Optional[str] = None
    guardrail_failed_check: Optional[str] = None
