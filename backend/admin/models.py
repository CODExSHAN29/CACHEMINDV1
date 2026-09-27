from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Tenant organization name")
    tenant_id: Optional[str] = Field(default=None, description="Optional custom tenant UUID")


class TenantResponse(BaseModel):
    id: str
    name: str
    is_active: bool
    created_at: datetime


class ProjectCreateRequest(BaseModel):
    tenant_id: str = Field(..., description="Parent tenant ID")
    name: str = Field(..., min_length=1, max_length=255, description="Project workspace name")
    project_id: Optional[str] = Field(default=None, description="Optional custom project UUID")


class ProjectResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    is_active: bool
    created_at: datetime


class APIKeyCreateRequest(BaseModel):
    project_id: str = Field(..., description="Parent project ID")
    name: str = Field(default="Live API Key", min_length=1, max_length=255)
    role: str = Field(default="admin", description="Role scope: admin, inference, read_only")


class APIKeyResponse(BaseModel):
    id: str
    project_id: str
    key_prefix: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None


class APIKeyCreateResult(BaseModel):
    id: str
    project_id: str
    key_prefix: str
    raw_api_key: str = Field(
        ...,
        description="The unhashed secret API key. Store this securely; it will NOT be shown again."
    )
    name: str
    role: str
    is_active: bool
    created_at: datetime


class ClusterStatsResponse(BaseModel):
    total_tenants: int
    total_projects: int
    total_api_keys: int
    total_cached_entries: int
    active_keys: int
