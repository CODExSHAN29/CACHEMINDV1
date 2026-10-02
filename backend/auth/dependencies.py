from datetime import datetime, timezone
from typing import Optional, Tuple
from fastapi import Depends, Header, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.auth.identity import AuthenticatedIdentity
from backend.auth.keys import hash_api_key
from backend.auth.session import hash_session_token, is_session_expired
from backend.db.models import Session, Tenant, TenantMembership, User
from backend.db.repositories import APIKeyRepository, SessionRepository
from backend.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_session_and_user(
    request: Request,
    auth: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Tuple[User, Session, Optional[TenantMembership], Optional[Tenant]]:
    """
    Authenticates active browser or API session via HTTP-only cookie or Bearer token.
    Returns (User, Session, active TenantMembership, active Tenant).
    Fails closed with HTTP 401 if unauthenticated or session expired.
    """
    raw_token: Optional[str] = None

    # 1. Check HTTP-only session cookie
    cookie_val = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if cookie_val:
        raw_token = cookie_val.strip()
    elif auth and auth.credentials:
        raw_token = auth.credentials.strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_hash = hash_session_token(raw_token)
    session_repo = SessionRepository(db)
    user_session = await session_repo.get_by_token_hash(token_hash)

    if not user_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Enforce session expiration
    if is_session_expired(user_session.expires_at):
        await session_repo.delete_session(token_hash)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = user_session.user
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or disabled.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Touch session activity
    try:
        await session_repo.touch_session(user_session.id)
    except Exception:
        pass

    # Resolve active workspace / tenant
    active_tenant: Optional[Tenant] = None
    active_membership: Optional[TenantMembership] = None

    if user_session.active_tenant_id:
        if user.memberships:
            for m in user.memberships:
                if m.tenant_id == user_session.active_tenant_id:
                    if m.tenant and m.tenant.is_active:
                        active_membership = m
                        active_tenant = m.tenant
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Selected workspace is inactive or disabled.",
                            headers={"WWW-Authenticate": "Bearer"},
                        )
                    break
        if not active_tenant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Selected workspace is inactive or inaccessible.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        # Fallback to first active workspace only when session.active_tenant_id is None
        if user.memberships:
            for m in user.memberships:
                if m.tenant and m.tenant.is_active:
                    active_membership = m
                    active_tenant = m.tenant
                    try:
                        await session_repo.update_active_tenant(user_session.id, active_tenant.id)
                    except Exception:
                        pass
                    break

    return user, user_session, active_membership, active_tenant


async def get_current_user(
    auth_data: Tuple[User, Session, Optional[TenantMembership], Optional[Tenant]] = Depends(
        get_current_session_and_user
    ),
) -> User:
    """Dependency that returns the current authenticated User."""
    return auth_data[0]


async def get_authenticated_identity(
    request: Request,
    auth: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    api_key_header: str | None = Header(None, alias="api-key"),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedIdentity:
    """
    Authenticates caller via Bearer token, api-key header, or active session cookie.
    Resolves API Key -> Project -> Tenant.
    Supports Master Admin Key for cluster management.
    Enforces active checks on API key, Project, and Tenant.
    Fails closed (HTTP 401) on any authentication or hierarchy failure.
    """
    raw_key: str | None = None
    if auth and auth.credentials:
        raw_key = auth.credentials.strip()
    elif api_key_header:
        raw_key = api_key_header.strip()

    # If no header key was provided, check for active session cookie
    if not raw_key:
        cookie_val = request.cookies.get(settings.SESSION_COOKIE_NAME)
        if cookie_val:
            token_hash = hash_session_token(cookie_val.strip())
            session_repo = SessionRepository(db)
            user_session = await session_repo.get_by_token_hash(token_hash)
            if (
                user_session
                and not is_session_expired(user_session.expires_at)
                and user_session.user
                and user_session.user.is_active
            ):
                user = user_session.user
                active_tenant: Optional[Tenant] = None
                role = "member"
                if user_session.active_tenant_id and user.memberships:
                    for m in user.memberships:
                        if m.tenant_id == user_session.active_tenant_id:
                            if m.tenant and m.tenant.is_active:
                                active_tenant = m.tenant
                                role = m.role
                            else:
                                raise HTTPException(
                                    status_code=status.HTTP_403_FORBIDDEN,
                                    detail="Selected workspace is inactive or inaccessible.",
                                    headers={"WWW-Authenticate": "Bearer"},
                                )
                            break
                    if not active_tenant:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Selected workspace is inactive or inaccessible.",
                            headers={"WWW-Authenticate": "Bearer"},
                        )
                elif user.memberships:
                    # Uninitialized session: fall back to first active workspace
                    for m in user.memberships:
                        if m.tenant and m.tenant.is_active:
                            active_tenant = m.tenant
                            role = m.role
                            break

                if active_tenant:
                    active_projects = [p for p in (active_tenant.projects or []) if p.is_active]
                    if not active_projects:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No active projects found in the selected workspace.",
                        )
                    project = None
                    if user_session.active_project_id:
                        for p in active_projects:
                            if p.id == user_session.active_project_id:
                                project = p
                                break
                    if not project:
                        project = active_projects[0]
                        try:
                            await session_repo.update_active_project(user_session.id, project.id)
                        except Exception:
                            pass
                    is_sysadmin = bool(user.is_superuser)

                    return AuthenticatedIdentity(
                        tenant_id=active_tenant.id,
                        project_id=project.id,
                        api_key_id="session_cookie_auth",
                        tenant_name=active_tenant.name,
                        project_name=project.name,
                        key_prefix="cm_sess",
                        role=role if role in ("owner", "admin") else ("admin" if is_sysadmin else "member"),
                        authority_type="session_user",
                        is_system_admin=is_sysadmin,
                    )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials. Provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Master Admin Key Bypass for administrative access
    if settings.ADMIN_MASTER_KEY and raw_key == settings.ADMIN_MASTER_KEY:
        return AuthenticatedIdentity(
            tenant_id="admin_tenant",
            project_id="admin_project",
            api_key_id="admin_master_key",
            tenant_name="CacheMind System Admin",
            project_name="Admin Control Plane",
            key_prefix="cm_admin",
            role="system_admin",
            authority_type="system_admin",
            is_system_admin=True,
        )

    key_hash = hash_api_key(raw_key)
    api_key_repo = APIKeyRepository(db)
    api_key = await api_key_repo.get_by_key_hash(key_hash)

    if not api_key:
        # Check if raw_key is a session token passed in Authorization: Bearer <session_token>
        session_repo = SessionRepository(db)
        token_hash = hash_session_token(raw_key)
        user_session = await session_repo.get_by_token_hash(token_hash)
        if (
            user_session
            and not is_session_expired(user_session.expires_at)
            and user_session.user
            and user_session.user.is_active
        ):
            user = user_session.user
            active_tenant = None
            role = "member"
            if user_session.active_tenant_id and user.memberships:
                for m in user.memberships:
                    if m.tenant_id == user_session.active_tenant_id:
                        if m.tenant and m.tenant.is_active:
                            active_tenant = m.tenant
                            role = m.role
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Selected workspace is inactive or inaccessible.",
                                headers={"WWW-Authenticate": "Bearer"},
                            )
                        break
                if not active_tenant:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Selected workspace is inactive or inaccessible.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            elif user.memberships:
                # Uninitialized session: fall back to first active workspace
                for m in user.memberships:
                    if m.tenant and m.tenant.is_active:
                        active_tenant = m.tenant
                        role = m.role
                        break

            if active_tenant:
                active_projects = [p for p in (active_tenant.projects or []) if p.is_active]
                if not active_projects:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No active projects found in the selected workspace.",
                    )
                project = None
                if user_session.active_project_id:
                    for p in active_projects:
                        if p.id == user_session.active_project_id:
                            project = p
                            break
                if not project:
                    project = active_projects[0]
                    try:
                        await session_repo.update_active_project(user_session.id, project.id)
                    except Exception:
                        pass
                is_sysadmin = bool(user.is_superuser)

                return AuthenticatedIdentity(
                    tenant_id=active_tenant.id,
                    project_id=project.id,
                    api_key_id="session_bearer_auth",
                    tenant_name=active_tenant.name,
                    project_name=project.name,
                    key_prefix="cm_sess",
                    role=role if role in ("owner", "admin") else ("admin" if is_sysadmin else "member"),
                    authority_type="session_user",
                    is_system_admin=is_sysadmin,
                )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unrecognized API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is disabled or revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    project = api_key.project
    if not project or not project.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Project associated with API key is inactive or not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tenant = project.tenant
    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant associated with API key is inactive or not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Record usage timestamp asynchronously
    try:
        await api_key_repo.update_last_used(api_key.id)
    except Exception:
        # Failing to record last_used should not abort the request
        pass

    return AuthenticatedIdentity(
        tenant_id=tenant.id,
        project_id=project.id,
        api_key_id=api_key.id,
        tenant_name=tenant.name,
        project_name=project.name,
        key_prefix=api_key.key_prefix,
        role=getattr(api_key, "role", "inference") or "inference",
        authority_type="project_key",
        is_system_admin=False,
    )


async def get_admin_identity(
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> AuthenticatedIdentity:
    """
    Enforces that caller has system administration privileges for cluster-level operations.
    """
    if not identity.can_system_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System administration privileges required.",
        )
    return identity
