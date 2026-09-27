from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.identity import AuthenticatedIdentity
from backend.auth.keys import hash_api_key
from backend.db.repositories import APIKeyRepository
from backend.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_authenticated_identity(
    auth: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    api_key_header: str | None = Header(None, alias="api-key"),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedIdentity:
    """
    Authenticates caller via Bearer token or api-key header.
    Resolves API Key -> Project -> Tenant.
    Enforces active checks on API key, Project, and Tenant.
    Fails closed (HTTP 401) on any authentication or hierarchy failure.
    """
    raw_key: str | None = None
    if auth and auth.credentials:
        raw_key = auth.credentials.strip()
    elif api_key_header:
        raw_key = api_key_header.strip()

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials. Provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    key_hash = hash_api_key(raw_key)
    api_key_repo = APIKeyRepository(db)
    api_key = await api_key_repo.get_by_key_hash(key_hash)

    if not api_key:
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
        role=getattr(api_key, "role", "admin") or "admin",
    )


async def get_admin_identity(
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> AuthenticatedIdentity:
    """
    Enforces that caller has admin role for administrative and provisioning operations.
    """
    if not identity.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for this endpoint.",
        )
    return identity

