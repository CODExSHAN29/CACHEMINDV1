from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class AnalyticsOverview(BaseModel):
    """
    High-level metrics summary for a tenant/project or global gateway instance.
    """
    total_requests: int = 0
    exact_hits: int = 0
    semantic_hits: int = 0
    total_hits: int = 0
    misses: int = 0
    errors: int = 0
    hit_rate_pct: float = 0.0

    total_tokens_processed: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    tokens_saved: int = 0
    input_tokens_saved: int = 0
    output_tokens_saved: int = 0

    estimated_cost_spent_usd: float = 0.0
    estimated_cost_saved_usd: float = 0.0
    net_savings_pct: float = 0.0

    latency_p50_ms: float = 0.0
    latency_p90_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    avg_gateway_latency_ms: float = 0.0
    avg_upstream_latency_ms: float = 0.0
    avg_cache_lookup_ms: float = 0.0
    time_saved_seconds: float = 0.0


class TimeseriesPoint(BaseModel):
    """
    Timeseries bucket data point for graphs and trend analysis.
    """
    timestamp: str
    total_requests: int = 0
    exact_hits: int = 0
    semantic_hits: int = 0
    misses: int = 0
    hit_rate_pct: float = 0.0
    tokens_saved: int = 0
    cost_saved_usd: float = 0.0
    avg_latency_ms: float = 0.0


class ModelUsageMetrics(BaseModel):
    """
    Model-specific metrics and distribution.
    """
    model: str
    provider: str
    total_requests: int = 0
    exact_hits: int = 0
    semantic_hits: int = 0
    misses: int = 0
    hit_rate_pct: float = 0.0
    tokens_saved: int = 0
    cost_saved_usd: float = 0.0
    cost_spent_usd: float = 0.0
    avg_latency_ms: float = 0.0


class RequestLogItem(BaseModel):
    """
    Single audit trail record for request log inspection.
    """
    id: str
    request_id: str
    tenant_id: str
    project_id: str
    provider: str
    requested_model: str
    actual_model: str
    cache_status: str
    exact_request_hash: str
    similarity_score: Optional[float] = None
    guardrail_status: Optional[bool] = None
    guardrail_failed_check: Optional[str] = None
    gateway_latency_ms: float
    upstream_latency_ms: Optional[float] = None
    exact_cache_lookup_ms: float
    upstream_called: bool
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: float = 0.0
    estimated_saved_usd: float = 0.0
    created_at: datetime


class PaginatedLogsResponse(BaseModel):
    """
    Paginated request logs response.
    """
    items: List[RequestLogItem]
    total: int
    page: int
    limit: int
    total_pages: int
