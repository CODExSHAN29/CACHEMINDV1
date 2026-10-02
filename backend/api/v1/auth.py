from datetime import datetime, timezone
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_session_and_user
from backend.auth.keys import generate_api_key
from backend.auth.password import hash_password, normalize_email, verify_password, needs_rehash
from backend.auth.session import (
    calculate_session_expiry,
    delete_session_cookie,
    generate_session_token,
    hash_session_token,
    set_session_cookie,
)
from backend.db.models import Session, Tenant, TenantMembership, User
from backend.db.repositories import (
    APIKeyRepository,
    ProjectRepository,
    SessionRepository,
    TenantMembershipRepository,
    TenantRepository,
    UserRepository,
)
from backend.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["Authentication & Workspaces"])


# --- Schemas ---

class SignUpRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Plaintext password (min 8 characters)")
    full_name: Optional[str] = Field(None, description="User full name")
    workspace_name: Optional[str] = Field(None, description="Optional initial workspace name")


class LoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="Plaintext password")


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Workspace name")


class SelectWorkspaceRequest(BaseModel):
    tenant_id: str = Field(..., description="Target tenant/workspace ID")


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    tenant_id: Optional[str] = Field(None, description="Tenant ID (defaults to active workspace)")


class CreateAPIKeyRequest(BaseModel):
    project_id: str = Field(..., description="Target project ID")
    name: Optional[str] = Field("Default Key", description="Display name for key")
    role: Optional[str] = Field("inference", description="Role (inference, read_only, cache_write, admin)")


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    is_superuser: bool
    created_at: datetime


class TenantResponse(BaseModel):
    id: str
    name: str
    role: str = "member"
    is_active: bool
    created_at: datetime


class ProjectResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    is_active: bool
    created_at: datetime


class APIKeyResponse(BaseModel):
    id: str
    project_id: str
    key_prefix: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None


class CreateAPIKeyResponse(APIKeyResponse):
    raw_key: str = Field(..., description="Full secret API key. Displayed ONCE upon generation.")


class AuthSessionResponse(BaseModel):
    user: UserResponse
    active_tenant: Optional[TenantResponse] = None
    active_project: Optional[ProjectResponse] = None
    workspaces: List[TenantResponse] = []
    projects: List[ProjectResponse] = []
    api_keys: List[APIKeyResponse] = []
    raw_api_key: Optional[str] = None


# --- Helpers ---

async def build_auth_session_response(
    user: User,
    session_obj: Optional[Session],
    db: AsyncSession,
    raw_api_key: Optional[str] = None,
) -> AuthSessionResponse:
    """Builds a complete workspace and session view for the authenticated user."""
    user_repo = UserRepository(db)
    # Refresh user with all memberships, tenants, and projects eager-loaded
    loaded_user = await user_repo.get_by_id(user.id)
    if not loaded_user:
        loaded_user = user

    workspaces: List[TenantResponse] = []
    active_tenant_obj: Optional[Tenant] = None
    active_tenant_role: str = "member"

    if loaded_user.memberships:
        for m in loaded_user.memberships:
            if m.tenant:
                t_resp = TenantResponse(
                    id=m.tenant.id,
                    name=m.tenant.name,
                    role=m.role,
                    is_active=m.tenant.is_active,
                    created_at=m.tenant.created_at,
                )
                workspaces.append(t_resp)
                if session_obj and session_obj.active_tenant_id and m.tenant.id == session_obj.active_tenant_id:
                    active_tenant_obj = m.tenant
                    active_tenant_role = m.role

        # Fallback to first workspace if none active
        if not active_tenant_obj and loaded_user.memberships and loaded_user.memberships[0].tenant:
            active_tenant_obj = loaded_user.memberships[0].tenant
            active_tenant_role = loaded_user.memberships[0].role

    active_tenant_resp: Optional[TenantResponse] = None
    if active_tenant_obj:
        active_tenant_resp = TenantResponse(
            id=active_tenant_obj.id,
            name=active_tenant_obj.name,
            role=active_tenant_role,
            is_active=active_tenant_obj.is_active,
            created_at=active_tenant_obj.created_at,
        )

    # Fetch projects for active tenant
    projects_resp: List[ProjectResponse] = []
    active_project_resp: Optional[ProjectResponse] = None
    api_keys_resp: List[APIKeyResponse] = []

    if active_tenant_obj:
        project_repo = ProjectRepository(db)
        projects = await project_repo.list_projects(active_tenant_obj.id)
        for p in projects:
            p_resp = ProjectResponse(
                id=p.id,
                tenant_id=p.tenant_id,
                name=p.name,
                is_active=p.is_active,
                created_at=p.created_at,
            )
            projects_resp.append(p_resp)

        if projects_resp:
            active_project_resp = projects_resp[0]
            # Fetch API keys for the active project
            api_key_repo = APIKeyRepository(db)
            keys = await api_key_repo.list_keys(active_project_resp.id)
            for k in keys:
                api_keys_resp.append(
                    APIKeyResponse(
                        id=k.id,
                        project_id=k.project_id,
                        key_prefix=k.key_prefix,
                        name=k.name,
                        role=k.role,
                        is_active=k.is_active,
                        created_at=k.created_at,
                        last_used_at=k.last_used_at,
                    )
                )

    user_resp = UserResponse(
        id=loaded_user.id,
        email=loaded_user.email,
        full_name=loaded_user.full_name,
        is_active=loaded_user.is_active,
        is_superuser=loaded_user.is_superuser,
        created_at=loaded_user.created_at,
    )

    return AuthSessionResponse(
        user=user_resp,
        active_tenant=active_tenant_resp,
        active_project=active_project_resp,
        workspaces=workspaces,
        projects=projects_resp,
        api_keys=api_keys_resp,
        raw_api_key=raw_api_key,
    )


# --- Endpoints ---

@router.post("/signup", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: SignUpRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Registers a new user, provisions a default workspace and project, generates an initial API key,
    and sets a secure HTTP-only session cookie.
    """
    clean_email = normalize_email(payload.email)
    if not clean_email or "@" not in clean_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid email address is required.",
        )

    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )

    user_repo = UserRepository(db)
    existing_user = await user_repo.get_by_email(clean_email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # 1. Create User
    pwd_hash = hash_password(payload.password)
    user = await user_repo.create_user(
        email=clean_email,
        password_hash=pwd_hash,
        full_name=payload.full_name,
    )

    # 2. Create Workspace / Tenant
    tenant_name = (
        payload.workspace_name.strip()
        if payload.workspace_name and payload.workspace_name.strip()
        else f"{payload.full_name or clean_email.split('@')[0]}'s Workspace"
    )
    tenant_repo = TenantRepository(db)
    tenant = await tenant_repo.create_tenant(name=tenant_name)

    # 3. Create Tenant Membership (Owner)
    membership_repo = TenantMembershipRepository(db)
    await membership_repo.create_membership(
        user_id=user.id,
        tenant_id=tenant.id,
        role="owner",
    )

    # 4. Create Default Project
    project_repo = ProjectRepository(db)
    project = await project_repo.create_project(
        tenant_id=tenant.id,
        name="Default Project",
    )

    # 5. Create Default Cryptographic API Key
    raw_key, key_prefix, key_hash = generate_api_key()
    api_key_repo = APIKeyRepository(db)
    await api_key_repo.create_api_key(
        project_id=project.id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name="Default Live Key",
        role="inference",
    )

    # 6. Create User Session
    raw_session_token = generate_session_token()
    token_hash = hash_session_token(raw_session_token)
    expires_at = calculate_session_expiry()
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    session_repo = SessionRepository(db)
    session_obj = await session_repo.create_session(
        session_token_hash=token_hash,
        user_id=user.id,
        active_tenant_id=tenant.id,
        expires_at=expires_at,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    # 7. Set HTTP-only Cookie
    set_session_cookie(response, raw_session_token)

    return await build_auth_session_response(
        user=user,
        session_obj=session_obj,
        db=db,
        raw_api_key=raw_key,
    )


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticates user with Argon2id password verification, establishes a new server session,
    and sets a secure HTTP-only cookie.
    """
    clean_email = normalize_email(payload.email)
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(clean_email)

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive or disabled.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if Argon2 parameters need upgrade
    if needs_rehash(user.password_hash):
        try:
            new_hash = hash_password(payload.password)
            await user_repo.update_password_hash(user.id, new_hash)
        except Exception as exc:
            logger.warning("Failed to rehash password: %s", exc)

    # Resolve active tenant from memberships
    active_tenant_id: Optional[str] = None
    if user.memberships:
        active_tenant_id = user.memberships[0].tenant_id

    # Create new session
    raw_session_token = generate_session_token()
    token_hash = hash_session_token(raw_session_token)
    expires_at = calculate_session_expiry()
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    session_repo = SessionRepository(db)
    session_obj = await session_repo.create_session(
        session_token_hash=token_hash,
        user_id=user.id,
        active_tenant_id=active_tenant_id,
        expires_at=expires_at,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    # Set HTTP-only Cookie
    set_session_cookie(response, raw_session_token)

    return await build_auth_session_response(
        user=user,
        session_obj=session_obj,
        db=db,
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Terminates the current session in the database and clears the HTTP-only cookie.
    """
    raw_token = request.cookies.get("cachemind_session")
    if not raw_token:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header[7:].strip()

    if raw_token:
        token_hash = hash_session_token(raw_token)
        session_repo = SessionRepository(db)
        await session_repo.delete_session(token_hash)

    delete_session_cookie(response)
    return {"status": "ok", "message": "Successfully logged out."}


@router.get("/me", response_model=AuthSessionResponse)
async def get_me(
    auth_data=Depends(get_current_session_and_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns the profile, active workspace, projects, and keys for the current authenticated user."""
    user, session_obj, _, _ = auth_data
    return await build_auth_session_response(
        user=user,
        session_obj=session_obj,
        db=db,
    )


@router.get("/workspaces", response_model=List[TenantResponse])
async def list_workspaces(
    auth_data=Depends(get_current_session_and_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists all workspaces/tenants that the current user belongs to."""
    user, _, _, _ = auth_data
    user_repo = UserRepository(db)
    loaded_user = await user_repo.get_by_id(user.id)
    if not loaded_user or not loaded_user.memberships:
        return []

    workspaces: List[TenantResponse] = []
    for m in loaded_user.memberships:
        if m.tenant:
            workspaces.append(
                TenantResponse(
                    id=m.tenant.id,
                    name=m.tenant.name,
                    role=m.role,
                    is_active=m.tenant.is_active,
                    created_at=m.tenant.created_at,
                )
            )
    return workspaces


@router.post("/workspaces", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: CreateWorkspaceRequest,
    auth_data=Depends(get_current_session_and_user),
    db: AsyncSession = Depends(get_db),
):
    """Creates a new workspace/tenant, adds user as owner, and sets up a default project."""
    user, session_obj, _, _ = auth_data
    tenant_name = payload.name.strip()
    if not tenant_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace name cannot be empty.",
        )

    tenant_repo = TenantRepository(db)
    tenant = await tenant_repo.create_tenant(name=tenant_name)

    membership_repo = TenantMembershipRepository(db)
    await membership_repo.create_membership(
        user_id=user.id,
        tenant_id=tenant.id,
        role="owner",
    )

    project_repo = ProjectRepository(db)
    project = await project_repo.create_project(
        tenant_id=tenant.id,
        name="Default Project",
    )

    raw_key, key_prefix, key_hash = generate_api_key()
    api_key_repo = APIKeyRepository(db)
    await api_key_repo.create_api_key(
        project_id=project.id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name="Default Live Key",
        role="inference",
    )

    session_repo = SessionRepository(db)
    await session_repo.update_active_tenant(session_obj.id, tenant.id)

    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        role="owner",
        is_active=tenant.is_active,
        created_at=tenant.created_at,
    )


@router.post("/workspaces/{tenant_id}/select", response_model=AuthSessionResponse)
@router.post("/workspaces/select", response_model=AuthSessionResponse)
async def select_workspace(
    tenant_id: Optional[str] = None,
    payload: Optional[SelectWorkspaceRequest] = None,
    auth_data=Depends(get_current_session_and_user),
    db: AsyncSession = Depends(get_db),
):
    """Switches the active workspace context for the current user session."""
    target_tenant_id = tenant_id or (payload.tenant_id if payload else None)
    if not target_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target tenant_id must be specified.",
        )

    user, session_obj, _, _ = auth_data
    membership_repo = TenantMembershipRepository(db)
    membership = await membership_repo.get_membership(user.id, target_tenant_id)

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this workspace.",
        )

    session_repo = SessionRepository(db)
    await session_repo.update_active_tenant(session_obj.id, target_tenant_id)
    session_obj.active_tenant_id = target_tenant_id

    return await build_auth_session_response(
        user=user,
        session_obj=session_obj,
        db=db,
    )


@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    tenant_id: Optional[str] = Query(None, description="Optional tenant ID filter"),
    auth_data=Depends(get_current_session_and_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists projects in the active or specified workspace."""
    user, session_obj, active_membership, active_tenant = auth_data
    target_tenant_id = tenant_id or (active_tenant.id if active_tenant else None)

    if not target_tenant_id:
        return []

    # Verify membership in target tenant
    membership_repo = TenantMembershipRepository(db)
    membership = await membership_repo.get_membership(user.id, target_tenant_id)
    if not membership and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to projects in this workspace is denied.",
        )

    project_repo = ProjectRepository(db)
    projects = await project_repo.list_projects(target_tenant_id)
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


@router.post("/projects", response_model=CreateAPIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: CreateProjectRequest,
    auth_data=Depends(get_current_session_and_user),
    db: AsyncSession = Depends(get_db),
):
    """Creates a new project within the active workspace and generates its primary API key."""
    user, _, active_membership, active_tenant = auth_data
    target_tenant_id = payload.tenant_id or (active_tenant.id if active_tenant else None)

    if not target_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active workspace found to create project in.",
        )

    membership_repo = TenantMembershipRepository(db)
    membership = await membership_repo.get_membership(user.id, target_tenant_id)
    if not membership or membership.role not in ("owner", "admin"):
        if not user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or owner role required to create projects.",
            )

    project_name = payload.name.strip()
    if not project_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project name cannot be empty.",
        )

    project_repo = ProjectRepository(db)
    project = await project_repo.create_project(
        tenant_id=target_tenant_id,
        name=project_name,
    )

    # Automatically issue primary API key
    raw_key, key_prefix, key_hash = generate_api_key()
    api_key_repo = APIKeyRepository(db)
    api_key = await api_key_repo.create_api_key(
        project_id=project.id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name="Primary Project Key",
        role="inference",
    )

    return CreateAPIKeyResponse(
        id=api_key.id,
        project_id=api_key.project_id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        role=api_key.role,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        raw_key=raw_key,
    )


@router.get("/keys", response_model=List[APIKeyResponse])
async def list_keys(
    project_id: Optional[str] = Query(None, description="Project ID filter"),
    auth_data=Depends(get_current_session_and_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists API keys for a project in the active workspace."""
    user, _, _, active_tenant = auth_data
    if not project_id:
        if not active_tenant:
            return []
        project_repo = ProjectRepository(db)
        projects = await project_repo.list_projects(active_tenant.id)
        if not projects:
            return []
        project_id = projects[0].id

    project_repo = ProjectRepository(db)
    project = await project_repo.get_project_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    membership_repo = TenantMembershipRepository(db)
    membership = await membership_repo.get_membership(user.id, project.tenant_id)
    if not membership and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to keys in this project is denied.",
        )

    api_key_repo = APIKeyRepository(db)
    keys = await api_key_repo.list_keys(project_id)
    return [
        APIKeyResponse(
            id=k.id,
            project_id=k.project_id,
            key_prefix=k.key_prefix,
            name=k.name,
            role=k.role,
            is_active=k.is_active,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
        )
        for k in keys
    ]


@router.post("/keys", response_model=CreateAPIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    payload: CreateAPIKeyRequest,
    auth_data=Depends(get_current_session_and_user),
    db: AsyncSession = Depends(get_db),
):
    """Generates a new cryptographic API key for the specified project."""
    user, _, _, _ = auth_data
    project_repo = ProjectRepository(db)
    project = await project_repo.get_project_by_id(payload.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    membership_repo = TenantMembershipRepository(db)
    membership = await membership_repo.get_membership(user.id, project.tenant_id)
    if not membership or membership.role not in ("owner", "admin"):
        if not user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or owner privileges required to create API keys.",
            )

    permitted_roles = {"inference", "read_only", "cache_write", "admin"}
    role = (payload.role or "inference").strip().lower()
    if role not in permitted_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid key role '{role}'. Permitted roles: {', '.join(sorted(permitted_roles))}",
        )

    raw_key, key_prefix, key_hash = generate_api_key()
    api_key_repo = APIKeyRepository(db)
    api_key = await api_key_repo.create_api_key(
        project_id=project.id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name=payload.name or "API Key",
        role=role,
    )

    return CreateAPIKeyResponse(
        id=api_key.id,
        project_id=api_key.project_id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        role=api_key.role,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        raw_key=raw_key,
    )


@router.delete("/keys/{key_id}")
async def revoke_key(
    key_id: str,
    auth_data=Depends(get_current_session_and_user),
    db: AsyncSession = Depends(get_db),
):
    """Revokes an active API key."""
    user, _, _, _ = auth_data
    api_key_repo = APIKeyRepository(db)
    api_key = await api_key_repo.get_by_id(key_id)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found.",
        )

    project = api_key.project
    if not project:
        project_repo = ProjectRepository(db)
        project = await project_repo.get_project_by_id(api_key.project_id)

    if project:
        membership_repo = TenantMembershipRepository(db)
        membership = await membership_repo.get_membership(user.id, project.tenant_id)
        if not membership or membership.role not in ("owner", "admin"):
            if not user.is_superuser:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin or owner privileges required to revoke API keys.",
                )

    success = await api_key_repo.revoke_key(key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to revoke API key.",
        )

    return {"status": "ok", "message": f"API key {key_id} successfully revoked."}
