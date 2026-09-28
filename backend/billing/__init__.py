"""
CacheMind Billing & Usage Metering Module (Pillar 4).

Integrates Stripe metered billing with CacheMind's FinOps analytics.
Tracks per-tenant request volume, token usage, and net dollar savings,
then reports metered usage events to Stripe for tiered subscription billing.

Usage tiers:
  - Starter:  10,000 requests / day  $49 / month
  - Pro:      100,000 requests / day $399 / month
  - Enterprise: 1,000,000 requests / day $2,999 / month
  - Custom:   Unlimited requests / day  (custom pricing)
"""

from .models import (
    BillingPlan,
    BillingPlanTier,
    MeteredUsageEvent,
    SubscriptionInfo,
    TierPricing,
    UsageSummary,
)
from .service import BillingService
from .webhooks import handle_stripe_webhook

__all__ = [
    "BillingPlan",
    "BillingPlanTier",
    "MeteredUsageEvent",
    "SubscriptionInfo",
    "TierPricing",
    "UsageSummary",
    "BillingService",
    "handle_stripe_webhook",
]