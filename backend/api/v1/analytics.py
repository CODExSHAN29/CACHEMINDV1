from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analytics.models import (
    AnalyticsOverview,
    ModelUsageMetrics,
    PaginatedLogsResponse,
    TimeseriesPoint,
)
from backend.analytics.service import AnalyticsService
from backend.app.config import settings
from backend.auth.dependencies import get_authenticated_identity
from backend.auth.identity import AuthenticatedIdentity
from backend.db.session import get_db

router = APIRouter(prefix="/v1/analytics", tags=["Analytics"])


def _resolve_scope(
    identity: AuthenticatedIdentity,
    tenant_id: Optional[str],
    project_id: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """
    Enforces multi-tenant data isolation.
    Tenants can only access their own telemetry unless they are the system development tenant.
    """
    if identity.tenant_id == settings.DEV_TENANT_ID:
        # Development / Admin tenant can query specific tenants or global metrics if not specified
        return tenant_id, project_id

    # Non-admin tenants are strictly scoped to their authenticated tenant
    if tenant_id and tenant_id != identity.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: cannot query analytics for another tenant.",
        )

    effective_tenant_id = identity.tenant_id
    effective_project_id = project_id or identity.project_id
    return effective_tenant_id, effective_project_id


@router.get("/overview", response_model=AnalyticsOverview)
async def get_analytics_overview(
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    project_id: Optional[str] = Query(None, description="Optional project filter"),
    start_time: Optional[datetime] = Query(None, description="ISO datetime start filter"),
    end_time: Optional[datetime] = Query(None, description="ISO datetime end filter"),
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsOverview:
    """
    Returns high-level KPI overview (requests, hit rate, latency percentiles, cost savings).
    """
    t_id, p_id = _resolve_scope(identity, tenant_id, project_id)
    service = AnalyticsService(db)
    return await service.get_overview(
        tenant_id=t_id,
        project_id=p_id,
        start_time=start_time,
        end_time=end_time,
    )


@router.get("/timeseries", response_model=List[TimeseriesPoint])
async def get_analytics_timeseries(
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    project_id: Optional[str] = Query(None, description="Optional project filter"),
    points: int = Query(24, ge=1, le=100, description="Number of bucket intervals"),
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
    db: AsyncSession = Depends(get_db),
) -> List[TimeseriesPoint]:
    """
    Returns grouped timeseries data points for trending graphs and analytics charts.
    """
    t_id, p_id = _resolve_scope(identity, tenant_id, project_id)
    service = AnalyticsService(db)
    return await service.get_timeseries(
        tenant_id=t_id,
        project_id=p_id,
        points=points,
    )


@router.get("/models", response_model=List[ModelUsageMetrics])
async def get_model_breakdown(
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    project_id: Optional[str] = Query(None, description="Optional project filter"),
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
    db: AsyncSession = Depends(get_db),
) -> List[ModelUsageMetrics]:
    """
    Returns usage, latency, and cost savings breakdown grouped by model and provider.
    """
    t_id, p_id = _resolve_scope(identity, tenant_id, project_id)
    service = AnalyticsService(db)
    return await service.get_model_breakdown(
        tenant_id=t_id,
        project_id=p_id,
    )


@router.get("/logs", response_model=PaginatedLogsResponse)
async def get_audit_logs(
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    project_id: Optional[str] = Query(None, description="Optional project filter"),
    cache_status: Optional[str] = Query(None, description="Filter by EXACT_HIT, L2_HIT, MISS, etc."),
    model: Optional[str] = Query(None, description="Filter by requested model"),
    search: Optional[str] = Query(None, description="Search term across request ID and exact hash"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=200, description="Number of logs per page"),
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
    db: AsyncSession = Depends(get_db),
) -> PaginatedLogsResponse:
    """
    Returns paginated audit logs with search and filtering capabilities.
    """
    t_id, p_id = _resolve_scope(identity, tenant_id, project_id)
    service = AnalyticsService(db)
    return await service.get_logs(
        tenant_id=t_id,
        project_id=p_id,
        cache_status=cache_status,
        model=model,
        search=search,
        page=page,
        limit=limit,
    )
