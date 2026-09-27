import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analytics.service import AnalyticsService
from backend.db.models import RequestLog


@pytest.mark.asyncio
async def test_analytics_service_empty_db(db_session: AsyncSession):
    service = AnalyticsService(db_session)
    overview = await service.get_overview()
    assert overview.total_requests == 0
    assert overview.hit_rate_pct == 0.0
    assert overview.total_hits == 0
    assert overview.estimated_cost_saved_usd == 0.0

    timeseries = await service.get_timeseries(points=12)
    assert len(timeseries) == 12

    models = await service.get_model_breakdown()
    assert len(models) == 0

    logs = await service.get_logs()
    assert logs.total == 0
    assert len(logs.items) == 0


@pytest.mark.asyncio
async def test_analytics_service_overview_aggregations(db_session: AsyncSession):
    # Insert test logs
    now = datetime.now(timezone.utc)
    logs_data = [
        # 1. Exact Hit: gpt-4o, 100 in, 100 out
        RequestLog(
            request_id=str(uuid.uuid4()),
            tenant_id="tenant_1",
            project_id="proj_1",
            provider="openai",
            requested_model="gpt-4o",
            actual_model="gpt-4o",
            cache_status="EXACT_HIT",
            exact_request_hash="hash1",
            gateway_latency_ms=1.5,
            upstream_latency_ms=None,
            exact_cache_lookup_ms=1.2,
            upstream_called=False,
            input_tokens=1000,
            output_tokens=1000,
            similarity_score=1.0,
            created_at=now - timedelta(minutes=10),
        ),
        # 2. L2 Hit: gpt-4o, 1000 in, 1000 out
        RequestLog(
            request_id=str(uuid.uuid4()),
            tenant_id="tenant_1",
            project_id="proj_1",
            provider="openai",
            requested_model="gpt-4o",
            actual_model="gpt-4o",
            cache_status="L2_HIT",
            exact_request_hash="hash2",
            gateway_latency_ms=12.0,
            upstream_latency_ms=None,
            exact_cache_lookup_ms=2.0,
            upstream_called=False,
            input_tokens=1000,
            output_tokens=1000,
            similarity_score=0.92,
            created_at=now - timedelta(minutes=5),
        ),
        # 3. Miss: gpt-4o, 1000 in, 1000 out
        RequestLog(
            request_id=str(uuid.uuid4()),
            tenant_id="tenant_1",
            project_id="proj_1",
            provider="openai",
            requested_model="gpt-4o",
            actual_model="gpt-4o",
            cache_status="MISS",
            exact_request_hash="hash3",
            gateway_latency_ms=850.0,
            upstream_latency_ms=800.0,
            exact_cache_lookup_ms=1.5,
            upstream_called=True,
            input_tokens=1000,
            output_tokens=1000,
            similarity_score=None,
            created_at=now - timedelta(minutes=1),
        ),
        # 4. Another tenant's log
        RequestLog(
            request_id=str(uuid.uuid4()),
            tenant_id="tenant_2",
            project_id="proj_2",
            provider="anthropic",
            requested_model="claude-3-5-sonnet-20241022",
            actual_model="claude-3-5-sonnet-20241022",
            cache_status="EXACT_HIT",
            exact_request_hash="hash4",
            gateway_latency_ms=2.0,
            upstream_latency_ms=None,
            exact_cache_lookup_ms=1.0,
            upstream_called=False,
            input_tokens=500,
            output_tokens=500,
            similarity_score=1.0,
            created_at=now,
        ),
    ]

    for item in logs_data:
        db_session.add(item)
    await db_session.commit()

    service = AnalyticsService(db_session)

    # Global overview (all tenants)
    global_overview = await service.get_overview()
    assert global_overview.total_requests == 4
    assert global_overview.exact_hits == 2
    assert global_overview.semantic_hits == 1
    assert global_overview.total_hits == 3
    assert global_overview.misses == 1
    assert global_overview.hit_rate_pct == 75.0
    assert global_overview.tokens_saved == 5000  # (2000 + 2000 + 1000)
    assert global_overview.estimated_cost_saved_usd > 0.0

    # Tenant 1 scoped overview
    t1_overview = await service.get_overview(tenant_id="tenant_1")
    assert t1_overview.total_requests == 3
    assert t1_overview.exact_hits == 1
    assert t1_overview.semantic_hits == 1
    assert t1_overview.misses == 1
    assert round(t1_overview.hit_rate_pct, 1) == 66.7
    assert t1_overview.tokens_saved == 4000


@pytest.mark.asyncio
async def test_analytics_service_models_and_logs(db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    log1 = RequestLog(
        request_id="req-test-1",
        tenant_id="tenant_a",
        project_id="proj_a",
        provider="openai",
        requested_model="gpt-4o",
        actual_model="gpt-4o",
        cache_status="EXACT_HIT",
        exact_request_hash="hash-abc",
        gateway_latency_ms=5.0,
        upstream_latency_ms=None,
        exact_cache_lookup_ms=1.0,
        upstream_called=False,
        input_tokens=200,
        output_tokens=300,
        created_at=now,
    )
    db_session.add(log1)
    await db_session.commit()

    service = AnalyticsService(db_session)

    # Models breakdown
    models = await service.get_model_breakdown(tenant_id="tenant_a")
    assert len(models) == 1
    assert models[0].model == "gpt-4o"
    assert models[0].total_requests == 1
    assert models[0].exact_hits == 1
    assert models[0].tokens_saved == 500

    # Logs pagination & search
    logs_res = await service.get_logs(tenant_id="tenant_a", search="req-test-1")
    assert logs_res.total == 1
    assert logs_res.items[0].request_id == "req-test-1"
    assert logs_res.items[0].cache_status == "EXACT_HIT"
    assert logs_res.items[0].estimated_saved_usd > 0
