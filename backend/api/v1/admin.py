import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.admin.models import (
    APIKeyCreateRequest,
    APIKeyCreateResult,
    APIKeyResponse,
    ClusterStatsResponse,
    ProjectCreateRequest,
    ProjectResponse,
    TenantCreateRequest,
    TenantResponse,
)
from backend.admin.service import AdminService
from backend.auth.dependencies import get_admin_identity
from backend.auth.identity import AuthenticatedIdentity
from backend.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["Admin & Provisioning"])


@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    req: TenantCreateRequest,
    admin: AuthenticatedIdentity = Depends(get_admin_identity),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """
    Provisions a new organization / tenant in CacheMind.
    Requires admin privileges.
    """
    return await AdminService.create_tenant(db, req)


@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    admin: AuthenticatedIdentity = Depends(get_admin_identity),
    db: AsyncSession = Depends(get_db),
) -> List[TenantResponse]:
    """
    Lists registered tenants.
    Requires admin privileges.
    """
    return await AdminService.list_tenants(db, limit=limit, offset=offset)


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    req: ProjectCreateRequest,
    admin: AuthenticatedIdentity = Depends(get_admin_identity),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Creates an isolated workspace / project under a tenant.
    Requires admin privileges.
    """
    try:
        return await AdminService.create_project(db, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    tenant_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    admin: AuthenticatedIdentity = Depends(get_admin_identity),
    db: AsyncSession = Depends(get_db),
) -> List[ProjectResponse]:
    """
    Lists projects, optionally filtered by tenant_id.
    Requires admin privileges.
    """
    return await AdminService.list_projects(db, tenant_id=tenant_id, limit=limit, offset=offset)


@router.post("/keys", response_model=APIKeyCreateResult, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    req: APIKeyCreateRequest,
    admin: AuthenticatedIdentity = Depends(get_admin_identity),
    db: AsyncSession = Depends(get_db),
) -> APIKeyCreateResult:
    """
    Generates a secure, cryptographically random API key for a project.
    Returns the plaintext raw_api_key exactly once upon creation.
    Requires admin privileges.
    """
    try:
        return await AdminService.create_api_key(db, req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    project_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    admin: AuthenticatedIdentity = Depends(get_admin_identity),
    db: AsyncSession = Depends(get_db),
) -> List[APIKeyResponse]:
    """
    Lists active and revoked API keys, optionally filtered by project_id.
    Requires admin privileges.
    """
    return await AdminService.list_api_keys(db, project_id=project_id, limit=limit, offset=offset)


@router.delete("/keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    admin: AuthenticatedIdentity = Depends(get_admin_identity),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Revokes an API key immediately. Revoked keys cannot authenticate inference or admin requests.
    Requires admin privileges.
    """
    revoked = await AdminService.revoke_api_key(db, key_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"API key '{key_id}' not found.")
    return {"success": True, "key_id": key_id, "revoked": True}


@router.get("/stats", response_model=ClusterStatsResponse)
async def get_cluster_stats(
    admin: AuthenticatedIdentity = Depends(get_admin_identity),
    db: AsyncSession = Depends(get_db),
) -> ClusterStatsResponse:
    """
    Provides cluster-wide summary statistics for tenants, projects, API keys, and cache volume.
    Requires admin privileges.
    """
    return await AdminService.get_cluster_stats(db)
