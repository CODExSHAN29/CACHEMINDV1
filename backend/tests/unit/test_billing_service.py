import pytest
from backend.billing.models import BillingPlanTier
from backend.billing.service import BillingService


def test_tier_pricing_retrieval():
    service = BillingService()
    pricing = service.get_tier_pricing(BillingPlanTier.PRO)
    assert pricing.name == "Pro"
    assert pricing.monthly_price_usd == 399.0
    assert pricing.daily_request_limit == 100_000

    custom = service.get_tier_pricing("custom")
    assert custom.tier == BillingPlanTier.CUSTOM


def test_list_tier_prices():
    service = BillingService()
    all_tiers = service.list_tier_prices()
    assert "starter" in all_tiers
    assert "pro" in all_tiers
    assert "enterprise" in all_tiers


def test_compute_usage_summary_and_overage():
    service = BillingService()
    summary = service.compute_usage_summary(
        tenant_id="test_tenant",
        tier=BillingPlanTier.STARTER,
        total_requests=15_000,  # exceeds 10,000 limit -> 5,000 overage
        exact_hits=5_000,
        l2_hits=5_000,
        misses=5_000,
        total_tokens_processed=12_000_000,  # exceeds 5,000,000 limit -> 7,000,000 overage
        total_tokens_saved=8_000_000,
        cost_spent_usd=10.0,
        cost_saved_usd=30.0,
    )
    assert summary.overage_requests == 5_000
    assert summary.overage_tokens == 7_000_000
    assert summary.estimated_overage_cost_usd > 0
    assert summary.net_savings_pct > 0


def test_record_and_process_usage_events():
    service = BillingService()
    event1 = service.record_usage_event("tenant_1", quantity=10, metric="requests")
    event2 = service.record_usage_event("tenant_1", quantity=5000, metric="tokens")

    unprocessed = service.get_unprocessed_events()
    assert len(unprocessed) == 2

    service.mark_events_processed([event1.event_id])
    remaining = service.get_unprocessed_events()
    assert len(remaining) == 1
    assert remaining[0].event_id == event2.event_id
