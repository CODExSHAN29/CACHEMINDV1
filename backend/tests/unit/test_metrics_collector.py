import pytest
from prometheus_client import CollectorRegistry

from backend.metrics.collector import MetricsCollector


def test_metrics_collector_custom_registry():
    registry = CollectorRegistry()
    collector = MetricsCollector(registry=registry)

    # 1. Record requests
    collector.record_request(
        tenant_id="tenant_1",
        provider="openai",
        model="gpt-4o",
        cache_status="EXACT_HIT",
        gateway_latency_ms=2.5,
        upstream_latency_ms=None,
        cache_lookup_ms=1.5,
        input_tokens=500,
        output_tokens=500,
    )

    collector.record_request(
        tenant_id="tenant_1",
        provider="openai",
        model="gpt-4o",
        cache_status="MISS",
        gateway_latency_ms=950.0,
        upstream_latency_ms=900.0,
        cache_lookup_ms=1.5,
        input_tokens=500,
        output_tokens=500,
    )

    # 2. Record rate limit rejection
    collector.record_rate_limit_rejection(tenant_id="tenant_1", limit_type="rpm")

    # 3. Record circuit breaker state
    collector.record_circuit_breaker_state(provider="anthropic", model="claude-3-5-sonnet", state="OPEN")

    # 4. Export OpenMetrics text
    exported_bytes = collector.export()
    exported_text = exported_bytes.decode("utf-8")

    assert "cachemind_requests_total" in exported_text
    assert 'cache_status="EXACT_HIT"' in exported_text
    assert 'cache_status="MISS"' in exported_text
    assert "cachemind_gateway_latency_seconds" in exported_text
    assert "cachemind_tokens_processed_total" in exported_text
    assert "cachemind_tokens_saved_total" in exported_text
    assert "cachemind_cost_saved_usd_total" in exported_text
    assert "cachemind_cost_spent_usd_total" in exported_text
    assert "cachemind_rate_limit_rejections_total" in exported_text
    assert "cachemind_circuit_breaker_state" in exported_text
