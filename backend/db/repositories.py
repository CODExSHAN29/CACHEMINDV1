from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models import APIKey, Project, RequestLog, Tenant, utc_now


class TenantRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_tenant(self, name: str, tenant_id: Optional[str] = None) -> Tenant:
        tenant = Tenant(name=name)
        if tenant_id:
            tenant.id = tenant_id
        self.session.add(tenant)
        await self.session.commit()
        await self.session.refresh(tenant)
        return tenant

    async def get_tenant_by_id(self, tenant_id: str) -> Optional[Tenant]:
        result = await self.session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def list_tenants(self, limit: int = 100, offset: int = 0) -> list[Tenant]:
        result = await self.session.execute(
            select(Tenant).order_by(Tenant.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_project(
        self, tenant_id: str, name: str, project_id: Optional[str] = None
    ) -> Project:
        project = Project(tenant_id=tenant_id, name=name)
        if project_id:
            project.id = project_id
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def get_project_by_id(self, project_id: str) -> Optional[Project]:
        result = await self.session.execute(
            select(Project).options(selectinload(Project.tenant)).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def list_projects(
        self, tenant_id: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> list[Project]:
        stmt = select(Project).options(selectinload(Project.tenant)).order_by(Project.created_at.desc())
        if tenant_id:
            stmt = stmt.where(Project.tenant_id == tenant_id)
        result = await self.session.execute(stmt.limit(limit).offset(offset))
        return list(result.scalars().all())


class APIKeyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_api_key(
        self,
        project_id: str,
        key_prefix: str,
        key_hash: str,
        name: str = "Default Key",
        role: str = "admin",
    ) -> APIKey:
        api_key = APIKey(
            project_id=project_id,
            key_prefix=key_prefix,
            key_hash=key_hash,
            name=name,
            role=role,
        )
        self.session.add(api_key)
        await self.session.commit()
        await self.session.refresh(api_key)
        return api_key

    async def get_by_key_hash(self, key_hash: str) -> Optional[APIKey]:
        result = await self.session.execute(
            select(APIKey)
            .options(
                selectinload(APIKey.project).selectinload(Project.tenant)
            )
            .where(APIKey.key_hash == key_hash)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, key_id: str) -> Optional[APIKey]:
        result = await self.session.execute(
            select(APIKey)
            .options(
                selectinload(APIKey.project).selectinload(Project.tenant)
            )
            .where(APIKey.id == key_id)
        )
        return result.scalar_one_or_none()

    async def list_keys(
        self, project_id: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> list[APIKey]:
        stmt = select(APIKey).options(
            selectinload(APIKey.project).selectinload(Project.tenant)
        ).order_by(APIKey.created_at.desc())
        if project_id:
            stmt = stmt.where(APIKey.project_id == project_id)
        result = await self.session.execute(stmt.limit(limit).offset(offset))
        return list(result.scalars().all())

    async def revoke_key(self, key_id: str) -> bool:
        result = await self.session.execute(
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(is_active=False)
        )
        await self.session.commit()
        return bool(result.rowcount > 0)

    async def update_last_used(self, api_key_id: str) -> None:
        await self.session.execute(
            update(APIKey)
            .where(APIKey.id == api_key_id)
            .values(last_used_at=utc_now())
        )
        await self.session.commit()


class RequestLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_log(
        self,
        request_id: str,
        tenant_id: str,
        project_id: str,
        provider: str,
        requested_model: str,
        actual_model: str,
        cache_status: str,
        exact_request_hash: str,
        gateway_latency_ms: float,
        upstream_latency_ms: Optional[float],
        exact_cache_lookup_ms: float,
        upstream_called: bool,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        similarity_score: Optional[float] = None,
        guardrail_status: Optional[bool] = None,
        guardrail_failed_check: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> RequestLog:
        log = RequestLog(
            request_id=request_id,
            tenant_id=tenant_id,
            project_id=project_id,
            provider=provider,
            requested_model=requested_model,
            actual_model=actual_model,
            cache_status=cache_status,
            exact_request_hash=exact_request_hash,
            similarity_score=similarity_score,
            guardrail_status=guardrail_status,
            guardrail_failed_check=guardrail_failed_check,
            gateway_latency_ms=gateway_latency_ms,
            upstream_latency_ms=upstream_latency_ms,
            exact_cache_lookup_ms=exact_cache_lookup_ms,
            upstream_called=upstream_called,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            created_at=created_at or utc_now(),
        )
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    async def get_by_request_id(self, request_id: str) -> Optional[RequestLog]:
        result = await self.session.execute(
            select(RequestLog).where(RequestLog.request_id == request_id)
        )
        return result.scalar_one_or_none()
