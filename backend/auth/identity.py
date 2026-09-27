from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedIdentity:
    """
    Cryptographically and server-authoritatively verified caller identity.
    tenant_id and project_id are strictly derived from the validated API key record
    and can NEVER be overridden by client request headers.
    """
    tenant_id: str
    project_id: str
    api_key_id: str
    tenant_name: str
    project_name: str
    key_prefix: str
    role: str = "admin"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

