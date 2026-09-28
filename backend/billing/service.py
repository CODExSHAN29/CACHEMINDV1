"""
Stripe Billing Service — Metered billing, tier enforcement,
usage tracking, and cost accounting for CacheMind (Pillar 4).
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Union

from backend.analytics.pricing import PricingEngine
from backend.billing.models import (
    BillingPlan,
    BillingPlanTier,
    MeteredUsageEvent,
    SubscriptionInfo,
    TIER_PRICING,
    TierPricing,
    UsageSummary,
)

logger = logging.getLogger("cachemind.billing")


class BillingService:
    """
    Enterprise-grade billing & metering service for CacheMind.
    Integrates with Stripe metered billing via webhook event pipeline.
    """

    def __init__(self):
        self._usage_events: list[MeteredUsageEvent] = []

    # ------------------------------------------------------------------
    # Tier & Pricing Access
    # ------------------------------------------------------------------

    @classmethod
    def get_tier_pricing(cls, tier: Union[BillingPlanTier, str]) -> TierPricing:
        tier = tier if isinstance(tier, BillingPlanTier) else BillingPlanTier(tier)
        return TIER_PRICING.get(tier, TIER_PRICING[BillingPlanTier.CUSTOM])

    @classmethod
    def list_tier_prices(cls) -> dict:
        return {tier.value: pricing.model_dump() for tier, pricing in TIER_PRICING.items()}

    # ------------------------------------------------------------------
    # Subscription Lifecycle (Stripe integration points)
    # ------------------------------------------------------------------

    def build_subscription_info(
        self,
        tenant_id: str,
        tier: BillingPlanTier = BillingPlanTier.STARTER,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
    ) -> SubscriptionInfo:
        return SubscriptionInfo(
            tenant_id=tenant_id,
            tier=tier,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
        )

    # ------------------------------------------------------------------
    # Usage Tracking & Enforcement
    # ------------------------------------------------------------------

    def compute_usage_summary(
        self,
        tenant_id: str,
        tier: BillingPlanTier,
        total_requests: int,
        exact_hits: int,
        l2_hits: int,
        misses: int,
        total_tokens_processed: int,
        total_tokens_saved: int,
        cost_spent_usd: float,
        cost_saved_usd: float,
    ) -> UsageSummary:
        pricing = self.get_tier_pricing(tier)
        req_limit = pricing.daily_request_limit if pricing.daily_request_limit > 0 else float("inf")
        tok_limit = pricing.daily_token_limit if pricing.daily_token_limit > 0 else float("inf")

        req_pct = (total_requests / req_limit * 100.0) if req_limit != float("inf") else 0.0
        tok_pct = (total_tokens_processed / tok_limit * 100.0) if tok_limit != float("inf") else 0.0

        overage_req = max(0, total_requests - req_limit) if req_limit != float("inf") else 0
        overage_tok = max(0, total_tokens_processed - tok_limit) if tok_limit != float("inf") else 0

        # Overage cost estimation (simple linear rate based on tier price)
        overage_cost = 0.0
        if pricing.tier == BillingPlanTier.STARTER:
            overage_cost = overage_req * 0.0005 + overage_tok * 0.0000025
        elif pricing.tier == BillingPlanTier.PRO:
            overage_cost = overage_req * 0.0003 + overage_tok * 0.0000015
        elif pricing.tier == BillingPlanTier.ENTERPRISE:
            overage_cost = 0.0  # Custom overage rates handled separately

        return UsageSummary(
            tenant_id=tenant_id,
            tier=tier,
            total_requests=total_requests,
            exact_hits=exact_hits,
            l2_hits=l2_hits,
            cache_misses=misses,
            total_tokens_processed=total_tokens_processed,
            total_tokens_saved=total_tokens_saved,
            upstream_cost_spent_usd=round(cost_spent_usd, 4),
            estimated_cost_saved_usd=round(cost_saved_usd, 4),
            net_savings_pct=round(
                (cost_saved_usd / max(cost_spent_usd + cost_saved_usd, 0.01)) * 100.0, 2
            ),
            daily_request_limit=pricing.daily_request_limit if pricing.daily_request_limit > 0 else -1,
            daily_token_limit=pricing.daily_token_limit if pricing.daily_token_limit > 0 else -1,
            usage_pct_of_request_limit=round(req_pct, 2),
            usage_pct_of_token_limit=round(tok_pct, 2),
            overage_requests=overage_req,
            overage_tokens=overage_tok,
            estimated_overage_cost_usd=round(overage_cost, 4),
        )

    def record_usage_event(
        self,
        tenant_id: str,
        subscription_item_id: Optional[str] = None,
        quantity: int = 1,
        metric: str = "requests",
    ) -> MeteredUsageEvent:
        event = MeteredUsageEvent(
            event_id=f"cm_usage_{uuid.uuid4().hex[:16]}",
            tenant_id=tenant_id,
            subscription_item_id=subscription_item_id,
            quantity=quantity,
            metric=metric,
        )
        self._usage_events.append(event)
        logger.info(
            "Usage event recorded: event_id=%s tenant=%s metric=%s qty=%d",
            event.event_id,
            tenant_id,
            metric,
            quantity,
        )
        return event

    def get_unprocessed_events(self) -> list[MeteredUsageEvent]:
        return [e for e in self._usage_events if not e.processed]

    def mark_events_processed(self, event_ids: list[str]) -> None:
        for event in self._usage_events:
            if event.event_id in event_ids:
                event.processed = True

    # ------------------------------------------------------------------
    # Revenue Metrics (derived from analytics service results)
    # ------------------------------------------------------------------

    def build_revenue_report(
        self,
        usage_summary: UsageSummary,
    ) -> dict:
        pricing = self.get_tier_pricing(usage_summary.tier)
        monthly_revenue = pricing.monthly_price_usd
        estimated_net_value = usage_summary.estimated_cost_saved_usd - usage_summary.upstream_cost_spent_usd
        return {
            "tier": usage_summary.tier.value,
            "monthly_subscription_usd": monthly_revenue,
            "upstream_cost_spent_usd": usage_summary.upstream_cost_spent_usd,
            "cost_saved_usd": usage_summary.estimated_cost_saved_usd,
            "net_customer_value_usd": round(estimated_net_value, 4),
            "request_usage_pct": usage_summary.usage_pct_of_request_limit,
            "token_usage_pct": usage_summary.usage_pct_of_token_limit,
            "overage_cost_estimate_usd": usage_summary.estimated_overage_cost_usd,
        }


def get_billing_service() -> BillingService:
    return BillingService()
