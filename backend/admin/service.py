import logging
from typing import List, Optional
from sqlalchemy import func, select
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
from backend.auth.keys import generate_api_key
from backend.caching.factory import get_cache_backend
from backend.db.models import APIKey, Project, Tenant
from backend.db.repositories import APIKeyRepository, ProjectRepository, TenantRepository

logger = logging.getLogger(__name__)


class AdminService:
    @staticmethod
    async def create_tenant(session: AsyncSession, req: TenantCreateRequest) -> TenantResponse:
        repo = TenantRepository(session)
        tenant = await repo.create_tenant(name=req.name, tenant_id=req.tenant_id)
        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            is_active=tenant.is_active,
            created_at=tenant.created_at,
        )

    @staticmethod
    async def list_tenants(session: AsyncSession, limit: int = 100, offset: int = 0) -> List[TenantResponse]:
        repo = TenantRepository(session)
        tenants = await repo.list_tenants(limit=limit, offset=offset)
        return [
            TenantResponse(
                id=t.id,
                name=t.name,
                is_active=t.is_active,
                created_at=t.created_at,
            )
            for t in tenants
        ]

    @staticmethod
    async def create_project(session: AsyncSession, req: ProjectCreateRequest) -> ProjectResponse:
        tenant_repo = TenantRepository(session)
        tenant = await tenant_repo.get_tenant_by_id(req.tenant_id)
        if not tenant:
            raise ValueError(f"Tenant '{req.tenant_id}' not found.")

        repo = ProjectRepository(session)
        project = await repo.create_project(
            tenant_id=req.tenant_id,
            name=req.name,
            project_id=req.project_id,
        )
        return ProjectResponse(
            id=project.id,
            tenant_id=project.tenant_id,
            name=project.name,
            is_active=project.is_active,
            created_at=project.created_at,
        )

    @staticmethod
    async def list_projects(
        session: AsyncSession, tenant_id: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List[ProjectResponse]:
        repo = ProjectRepository(session)
        projects = await repo.list_projects(tenant_id=tenant_id, limit=limit, offset=offset)
        return [
            ProjectResponse(
                id=p.id,
                tenant_id=p.tenant_id,
                name=p.name,
                is_active=p.is_active,
                created_at=p.created_at,
            )
            for p in projects
        ]

    @staticmethod
    async def create_api_key(session: AsyncSession, req: APIKeyCreateRequest) -> APIKeyCreateResult:
        project_repo = ProjectRepository(session)
        project = await project_repo.get_project_by_id(req.project_id)
        if not project:
            raise ValueError(f"Project '{req.project_id}' not found.")

        raw_key, key_prefix, key_hash = generate_api_key()
        api_key_repo = APIKeyRepository(session)
        api_key = await api_key_repo.create_api_key(
            project_id=req.project_id,
            key_prefix=key_prefix,
            key_hash=key_hash,
            name=req.name,
            role=req.role,
        )

        return APIKeyCreateResult(
            id=api_key.id,
            project_id=api_key.project_id,
            key_prefix=api_key.key_prefix,
            raw_api_key=raw_key,
            name=api_key.name,
            role=getattr(api_key, "role", req.role) or req.role,
            is_active=api_key.is_active,
            created_at=api_key.created_at,
        )

    @staticmethod
    async def list_api_keys(
        session: AsyncSession, project_id: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List[APIKeyResponse]:
        repo = APIKeyRepository(session)
        keys = await repo.list_keys(project_id=project_id, limit=limit, offset=offset)
        return [
            APIKeyResponse(
                id=k.id,
                project_id=k.project_id,
                key_prefix=k.key_prefix,
                name=k.name,
                role=getattr(k, "role", "admin") or "admin",
                is_active=k.is_active,
                created_at=k.created_at,
                last_used_at=k.last_used_at,
            )
            for k in keys
        ]

    @staticmethod
    async def revoke_api_key(session: AsyncSession, key_id: str) -> bool:
        repo = APIKeyRepository(session)
        return await repo.revoke_key(key_id)

    @staticmethod
    async def get_cluster_stats(session: AsyncSession) -> ClusterStatsResponse:
        t_res = await session.execute(select(func.count(Tenant.id)))
        total_tenants = t_res.scalar() or 0

        p_res = await session.execute(select(func.count(Project.id)))
        total_projects = p_res.scalar() or 0

        k_res = await session.execute(select(func.count(APIKey.id)))
        total_api_keys = k_res.scalar() or 0

        ak_res = await session.execute(select(func.count(APIKey.id)).where(APIKey.is_active == True))
        active_keys = ak_res.scalar() or 0

        # Cached entries count across backend
        cached_count = 0
        try:
            cache_backend = get_cache_backend()
            if hasattr(cache_backend, "_store"):
                cached_count = len(cache_backend._store)
        except Exception:
            pass

        return ClusterStatsResponse(
            total_tenants=total_tenants,
            total_projects=total_projects,
            total_api_keys=total_api_keys,
            total_cached_entries=cached_count,
            active_keys=active_keys,
        )
