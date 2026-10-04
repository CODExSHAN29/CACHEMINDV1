from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, Optional


@dataclass
class InferenceResult:
    """Domain model representing the transport-neutral result of an inference execution."""

    request_id: str
    cache_status: str  # "EXACT_HIT" | "L2_HIT" | "MISS"
    provider: str
    model: str
    exact_request_hash: str
    gateway_latency_ms: float
    exact_cache_lookup_ms: float
    headers: Dict[str, str] = field(default_factory=dict)
    response_body: Optional[Dict[str, Any]] = None
    stream_generator: Optional[AsyncIterator[str]] = None
    is_stream: bool = False
    upstream_latency_ms: Optional[float] = None
    fallback_hops: int = 0
    was_coalesced: bool = False
    similarity_score: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    scope_hash: Optional[str] = None
