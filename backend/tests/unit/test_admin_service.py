import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.admin.models import (
    APIKeyCreateRequest,
    ProjectCreateRequest,
    TenantCreateRequest,
)
from backend.admin.service import AdminService


@pytest.mark.asyncio
async def test_admin_tenant_lifecycle(db_session: AsyncSession):
    # 1. Create Tenant
    req = TenantCreateRequest(name="Acme Corporation")
    tenant = await AdminService.create_tenant(db_session, req)
    assert tenant.name == "Acme Corporation"
    assert tenant.is_active is True
    assert tenant.id is not None

    # 2. List Tenants
    tenants = await AdminService.list_tenants(db_session)
    assert len(tenants) == 1
    assert tenants[0].id == tenant.id


@pytest.mark.asyncio
async def test_admin_project_lifecycle(db_session: AsyncSession):
    # 1. Create Tenant
    t_req = TenantCreateRequest(name="Project Test Tenant")
    tenant = await AdminService.create_tenant(db_session, t_req)

    # 2. Create Project
    p_req = ProjectCreateRequest(tenant_id=tenant.id, name="Project Alpha")
    project = await AdminService.create_project(db_session, p_req)
    assert project.name == "Project Alpha"
    assert project.tenant_id == tenant.id
    assert project.is_active is True

    # 3. List Projects
    projects = await AdminService.list_projects(db_session, tenant_id=tenant.id)
    assert len(projects) == 1
    assert projects[0].id == project.id


@pytest.mark.asyncio
async def test_admin_api_key_lifecycle(db_session: AsyncSession):
    # 1. Setup Tenant and Project
    tenant = await AdminService.create_tenant(db_session, TenantCreateRequest(name="Key Corp"))
    project = await AdminService.create_project(
        db_session, ProjectCreateRequest(tenant_id=tenant.id, name="Key Project")
    )

    # 2. Create API Key
    k_req = APIKeyCreateRequest(project_id=project.id, name="Production Inference Key", role="inference")
    key_result = await AdminService.create_api_key(db_session, k_req)
    assert key_result.project_id == project.id
    assert key_result.raw_api_key.startswith("cm_live_")
    assert key_result.role == "inference"
    assert key_result.is_active is True

    # 3. List API Keys
    keys = await AdminService.list_api_keys(db_session, project_id=project.id)
    assert len(keys) == 1
    assert keys[0].id == key_result.id
    assert keys[0].role == "inference"

    # 4. Revoke API Key
    revoked = await AdminService.revoke_api_key(db_session, key_result.id)
    assert revoked is True

    # Verify inactive
    keys_after = await AdminService.list_api_keys(db_session, project_id=project.id)
    assert keys_after[0].is_active is False


@pytest.mark.asyncio
async def test_admin_cluster_stats(db_session: AsyncSession):
    tenant = await AdminService.create_tenant(db_session, TenantCreateRequest(name="Stats Corp"))
    project = await AdminService.create_project(
        db_session, ProjectCreateRequest(tenant_id=tenant.id, name="Stats Project")
    )
    await AdminService.create_api_key(
        db_session, APIKeyCreateRequest(project_id=project.id, name="Stats Key")
    )

    stats = await AdminService.get_cluster_stats(db_session)
    assert stats.total_tenants == 1
    assert stats.total_projects == 1
    assert stats.total_api_keys == 1
    assert stats.active_keys == 1
