import logging
from typing import Optional
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    REGISTRY,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

from backend.analytics.pricing import PricingEngine

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Prometheus metrics collector and exporter for CacheMind.
    Tracks request volumes, latency distributions, cache efficiency,
    financial savings, circuit breakers, and rate limits.
    """

    def __init__(self, registry: Optional[CollectorRegistry] = None) -> None:
        self.registry = registry or REGISTRY
        self._init_metrics()

    def _init_metrics(self) -> None:
        # Avoid double-registration error if re-initialized with standard REGISTRY
        try:
            self.requests_total = Counter(
                "cachemind_requests_total",
                "Total requests processed by the CacheMind gateway",
                ["provider", "model", "cache_status", "tenant_id"],
                registry=self.registry,
            )
            self.gateway_latency = Histogram(
                "cachemind_gateway_latency_seconds",
                "Total gateway end-to-end latency in seconds",
                ["provider", "model", "cache_status"],
                buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
                registry=self.registry,
            )
            self.upstream_latency = Histogram(
                "cachemind_upstream_latency_seconds",
                "Upstream LLM provider latency in seconds",
                ["provider", "model"],
                buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
                registry=self.registry,
            )
            self.cache_lookup_latency = Histogram(
                "cachemind_cache_lookup_latency_seconds",
                "Cache lookup latency in seconds",
                ["cache_level"],
                buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1),
                registry=self.registry,
            )
            self.tokens_processed = Counter(
                "cachemind_tokens_processed_total",
                "Total LLM tokens processed",
                ["token_type", "cache_status"],
                registry=self.registry,
            )
            self.tokens_saved = Counter(
                "cachemind_tokens_saved_total",
                "Total LLM tokens saved via cache hits",
                ["tenant_id", "model"],
                registry=self.registry,
            )
            self.cost_saved_usd = Counter(
                "cachemind_cost_saved_usd_total",
                "Total estimated USD cost saved via cache hits",
                ["tenant_id", "model"],
                registry=self.registry,
            )
            self.cost_spent_usd = Counter(
                "cachemind_cost_spent_usd_total",
                "Total estimated USD cost spent on upstream LLMs",
                ["tenant_id", "model"],
                registry=self.registry,
            )
            self.rate_limit_rejections = Counter(
                "cachemind_rate_limit_rejections_total",
                "Total requests rejected due to rate limits",
                ["tenant_id", "limit_type"],
                registry=self.registry,
            )
            self.circuit_breaker_state = Gauge(
                "cachemind_circuit_breaker_state",
                "Circuit breaker state: 0=CLOSED, 1=HALF_OPEN, 2=OPEN",
                ["provider", "model"],
                registry=self.registry,
            )
            self.errors_total = Counter(
                "cachemind_errors_total",
                "Total runtime errors encountered by CacheMind gateway",
                ["error_type", "tenant_id"],
                registry=self.registry,
            )
        except ValueError as err:
            logger.debug("Metrics already registered in Prometheus registry: %s", err)

    def record_request(
        self,
        tenant_id: str,
        provider: str,
        model: str,
        cache_status: str,
        gateway_latency_ms: float,
        upstream_latency_ms: Optional[float] = None,
        cache_lookup_ms: Optional[float] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
    ) -> None:
        """
        Records all metrics associated with an inference request.
        """
        prov = provider or "unknown"
        mdl = model or "unknown"
        status = cache_status or "MISS"
        t_id = tenant_id or "default"

        in_tok = input_tokens or 0
        out_tok = output_tokens or 0

        # Request count & gateway latency
        self.requests_total.labels(provider=prov, model=mdl, cache_status=status, tenant_id=t_id).inc()
        self.gateway_latency.labels(provider=prov, model=mdl, cache_status=status).observe(gateway_latency_ms / 1000.0)

        # Upstream latency
        if upstream_latency_ms is not None:
            self.upstream_latency.labels(provider=prov, model=mdl).observe(upstream_latency_ms / 1000.0)

        # Cache lookup latency
        if cache_lookup_ms is not None:
            level = "L2" if status == "L2_HIT" else "L1"
            self.cache_lookup_latency.labels(cache_level=level).observe(cache_lookup_ms / 1000.0)

        # Tokens
        if in_tok > 0:
            self.tokens_processed.labels(token_type="input", cache_status=status).inc(in_tok)
        if out_tok > 0:
            self.tokens_processed.labels(token_type="output", cache_status=status).inc(out_tok)

        # Cost & Savings
        if status in ("EXACT_HIT", "L2_HIT"):
            saved_tokens = in_tok + out_tok
            if saved_tokens > 0:
                self.tokens_saved.labels(tenant_id=t_id, model=mdl).inc(saved_tokens)
            savings_usd = PricingEngine.calculate_savings(mdl, in_tok, out_tok)
            if savings_usd > 0:
                self.cost_saved_usd.labels(tenant_id=t_id, model=mdl).inc(savings_usd)
        elif upstream_latency_ms is not None:
            cost_usd = PricingEngine.calculate_cost(mdl, in_tok, out_tok)
            if cost_usd > 0:
                self.cost_spent_usd.labels(tenant_id=t_id, model=mdl).inc(cost_usd)

    def record_rate_limit_rejection(self, tenant_id: str, limit_type: str = "rpm") -> None:
        """
        Records a rate-limit rejection event.
        """
        t_id = tenant_id or "default"
        self.rate_limit_rejections.labels(tenant_id=t_id, limit_type=limit_type).inc()

    def record_circuit_breaker_state(self, provider: str, model: str, state: str) -> None:
        """
        Updates the circuit breaker state gauge:
        CLOSED = 0, HALF_OPEN = 1, OPEN = 2
        """
        state_map = {"CLOSED": 0, "HALF_OPEN": 1, "OPEN": 2}
        val = state_map.get(state.upper(), 0)
        self.circuit_breaker_state.labels(provider=provider or "unknown", model=model or "unknown").set(val)

    def record_error(self, error_type: str, tenant_id: str = "default") -> None:
        """
        Records an error event counter in Prometheus metrics.
        """
        t_id = tenant_id or "default"
        err_type = error_type or "unknown"
        self.errors_total.labels(error_type=err_type, tenant_id=t_id).inc()

    def export(self) -> bytes:
        """
        Exports the current metrics in Prometheus text format.
        """
        return generate_latest(self.registry)


# Global Singleton Collector
_default_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    global _default_collector
    if _default_collector is None:
        _default_collector = MetricsCollector()
    return _default_collector
