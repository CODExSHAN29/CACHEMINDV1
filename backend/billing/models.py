"""
Pydantic models for CacheMind Billing & Metering (Pillar 4).
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field


class BillingPlanTier(str, Enum):
    """Supported billing subscription tiers."""
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class TierPricing(BaseModel):
    """Pricing and limits for a single subscription tier."""
    tier: BillingPlanTier
    name: str
    monthly_price_usd: float
    daily_request_limit: int
    daily_token_limit: int
    max_models: int
    max_tenants: int
    max_projects_per_tenant: int
    max_api_keys_per_project: int
    semantic_cache_enabled: bool = True
    pii_masking_enabled: bool = True
    sse_streaming_enabled: bool = True
    observability_dashboard_enabled: bool = True
    admin_api_enabled: bool = False
    sso_enabled: bool = False
    sla_uptime_pct: float = 99.9
    support_level: str = "email"


# Default tier catalog
TIER_PRICING: Dict[BillingPlanTier, TierPricing] = {
    BillingPlanTier.STARTER: TierPricing(
        tier=BillingPlanTier.STARTER,
        name="Starter",
        monthly_price_usd=49.0,
        daily_request_limit=10_000,
        daily_token_limit=5_000_000,
        max_models=2,
        max_tenants=1,
        max_projects_per_tenant=1,
        max_api_keys_per_project=3,
        semantic_cache_enabled=True,
        pii_masking_enabled=True,
        sse_streaming_enabled=True,
        observability_dashboard_enabled=True,
        admin_api_enabled=False,
        sso_enabled=False,
        sla_uptime_pct=99.5,
        support_level="community",
    ),
    BillingPlanTier.PRO: TierPricing(
        tier=BillingPlanTier.PRO,
        name="Pro",
        monthly_price_usd=399.0,
        daily_request_limit=100_000,
        daily_token_limit=50_000_000,
        max_models=10,
        max_tenants=5,
        max_projects_per_tenant=10,
        max_api_keys_per_project=25,
        semantic_cache_enabled=True,
        pii_masking_enabled=True,
        sse_streaming_enabled=True,
        observability_dashboard_enabled=True,
        admin_api_enabled=True,
        sso_enabled=False,
        sla_uptime_pct=99.9,
        support_level="email",
    ),
    BillingPlanTier.ENTERPRISE: TierPricing(
        tier=BillingPlanTier.ENTERPRISE,
        name="Enterprise",
        monthly_price_usd=2_999.0,
        daily_request_limit=1_000_000,
        daily_token_limit=500_000_000,
        max_models=50,
        max_tenants=100,
        max_projects_per_tenant=100,
        max_api_keys_per_project=200,
        semantic_cache_enabled=True,
        pii_masking_enabled=True,
        sse_streaming_enabled=True,
        observability_dashboard_enabled=True,
        admin_api_enabled=True,
        sso_enabled=True,
        sla_uptime_pct=99.99,
        support_level="dedicated",
    ),
    BillingPlanTier.CUSTOM: TierPricing(
        tier=BillingPlanTier.CUSTOM,
        name="Custom",
        monthly_price_usd=0.0,
        daily_request_limit=-1,
        daily_token_limit=-1,
        max_models=-1,
        max_tenants=-1,
        max_projects_per_tenant=-1,
        max_api_keys_per_project=-1,
        semantic_cache_enabled=True,
        pii_masking_enabled=True,
        sse_streaming_enabled=True,
        observability_dashboard_enabled=True,
        admin_api_enabled=True,
        sso_enabled=True,
        sla_uptime_pct=99.99,
        support_level="dedicated",
    ),
}


class BillingPlan(BaseModel):
    """A tenant's active subscription plan."""
    tenant_id: str
    tier: BillingPlanTier
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    stripe_subscription_item_id: Optional[str] = None
    status: str = "active"  # active, trialing, past_due, cancelled, incomplete
    trial_ends_at: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UsageSummary(BaseModel):
    """Aggregated usage metrics for a billing period."""
    tenant_id: str
    tier: BillingPlanTier
    total_requests: int = 0
    exact_hits: int = 0
    l2_hits: int = 0
    cache_misses: int = 0
    total_tokens_processed: int = 0
    total_tokens_saved: int = 0
    upstream_cost_spent_usd: float = 0.0
    estimated_cost_saved_usd: float = 0.0
    net_savings_pct: float = 0.0
    daily_request_limit: int = 0
    daily_token_limit: int = 0
    usage_pct_of_request_limit: float = 0.0
    usage_pct_of_token_limit: float = 0.0
    overage_requests: int = 0
    overage_tokens: int = 0
    estimated_overage_cost_usd: float = 0.0


class MeteredUsageEvent(BaseModel):
    """A single metered usage event sent to Stripe."""
    event_id: str
    tenant_id: str
    subscription_item_id: Optional[str] = None
    quantity: int
    metric: str  # requests | tokens_saved | cost_saved_usd
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    stripe_event_id: Optional[str] = None
    processed: bool = False


class SubscriptionInfo(BaseModel):
    """Stripe subscription metadata for a tenant."""
    tenant_id: str
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    stripe_subscription_item_id: Optional[str] = None
    tier: BillingPlanTier
    status: str = "incomplete"
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at: Optional[datetime] = None
    cancel_at_period_end: bool = False
    trial_end: Optional[datetime] = None