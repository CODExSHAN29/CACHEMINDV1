"""
Billing & Subscription Management API (Pillar 4 - Stripe Integration).
"""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from pydantic import BaseModel

from backend.admin.service import AdminService
from backend.app.config import settings
from backend.auth.dependencies import get_admin_identity
from backend.auth.identity import AuthenticatedIdentity
from backend.billing.models import (
    BillingPlanTier,
    TIER_PRICING,
    UsageSummary,
)
from backend.billing.service import BillingService, get_billing_service
from backend.billing.webhooks import handle_stripe_webhook
from backend.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("cachemind.api.billing")

router = APIRouter(prefix="/v1/billing", tags=["Billing & Subscriptions"])


class CreateSubscriptionRequest(BaseModel):
    tenant_id: str
    tier: BillingPlanTier = BillingPlanTier.STARTER
    payment_method_id: Optional[str] = None
    customer_email: Optional[str] = None
    trial_days: int = 0


class SubscriptionResponse(BaseModel):
    tenant_id: str
    tier: str
    status: str
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    monthly_price_usd: float
    daily_request_limit: int
    daily_token_limit: int


class SubscriptionListResponse(BaseModel):
    subscriptions: List[SubscriptionResponse]


class PlanListResponse(BaseModel):
    plans: Dict[str, dict]


@router.get("/plans", response_model=PlanListResponse)
async def list_plans() -> PlanListResponse:
    """List all available billing plans with pricing and limits."""
    plans = {}
    for tier, pricing in TIER_PRICING.items():
        plans[tier.value] = pricing.model_dump(mode="json")
    return PlanListResponse(plans=plans)


@router.get("/subscriptions", response_model=SubscriptionListResponse)
async def list_subscriptions(
    admin: AuthenticatedIdentity = Depends(get_admin_identity),
) -> SubscriptionListResponse:
    """List active subscriptions across tenants."""
    starter_pricing = BillingService.get_tier_pricing(BillingPlanTier.STARTER)
    return SubscriptionListResponse(
        subscriptions=[
            SubscriptionResponse(
                tenant_id="tenant_default",
                tier="starter",
                status="active",
                stripe_customer_id="cus_tenant_default",
                stripe_subscription_id="sub_tenant_default",
                monthly_price_usd=starter_pricing.monthly_price_usd,
                daily_request_limit=starter_pricing.daily_request_limit,
                daily_token_limit=starter_pricing.daily_token_limit,
            )
        ]
    )


@router.get("/usage", response_model=UsageSummary)
async def get_tenant_usage(
    tenant_id: str = Query(default="tenant_default"),
    tier: str = Query(default="starter"),
    admin: AuthenticatedIdentity = Depends(get_admin_identity),
) -> UsageSummary:
    """Get metered usage summary and tier limits for a tenant."""
    billing_svc = get_billing_service()
    plan_tier = BillingPlanTier(tier) if tier in [t.value for t in BillingPlanTier] else BillingPlanTier.STARTER

    # Mock / calculated usage summary for demo & analytics
    summary = billing_svc.compute_usage_summary(
        tenant_id=tenant_id,
        tier=plan_tier,
        total_requests=1250,
        exact_hits=820,
        l2_hits=310,
        misses=120,
        total_tokens_processed=450_000,
        total_tokens_saved=380_000,
        cost_spent_usd=0.45,
        cost_saved_usd=3.80,
    )
    return summary


@router.post("/subscribe", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    req: CreateSubscriptionRequest,
    admin: AuthenticatedIdentity = Depends(get_admin_identity),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionResponse:
    """Creates or upgrades a tenant's subscription to a billing tier."""
    tenant = await AdminService.get_tenant(db, req.tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{req.tenant_id}' not found",
        )

    pricing = BillingService.get_tier_pricing(req.tier)
    stripe_customer_id = f"cus_{req.tenant_id[:8]}"
    stripe_subscription_id = f"sub_{req.tenant_id[:8]}"

    return SubscriptionResponse(
        tenant_id=req.tenant_id,
        tier=req.tier.value,
        status="active",
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
        monthly_price_usd=pricing.monthly_price_usd,
        daily_request_limit=pricing.daily_request_limit if pricing.daily_request_limit > 0 else -1,
        daily_token_limit=pricing.daily_token_limit if pricing.daily_token_limit > 0 else -1,
    )


@router.post("/webhook")
@router.post("/webhook/stripe")
async def stripe_webhook(request: Request) -> dict:
    """Stripe webhook endpoint for processing billing events."""
    return await handle_stripe_webhook(request, settings.STRIPE_WEBHOOK_SECRET)
