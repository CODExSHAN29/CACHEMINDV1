from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AuthenticatedIdentity:
    """
    Cryptographically and server-authoritatively verified caller identity.
    tenant_id and project_id are strictly derived from the validated API key record
    or session context and can NEVER be overridden by client request headers.
    """
    tenant_id: str
    project_id: str
    api_key_id: str
    tenant_name: str
    project_name: str
    key_prefix: str
    role: str = "inference"
    authority_type: Literal["project_key", "session_user", "system_admin"] = "project_key"
    is_system_admin: bool = False

    @property
    def can_infer(self) -> bool:
        if self.is_system_admin:
            return True
        return self.role in ("inference", "cache_write", "admin", "owner", "member")

    @property
    def can_read_cache(self) -> bool:
        return True

    @property
    def can_write_cache(self) -> bool:
        if self.is_system_admin:
            return True
        return self.role in ("cache_write", "admin", "owner")

    @property
    def can_manage_project(self) -> bool:
        if self.is_system_admin:
            return True
        if self.authority_type == "session_user":
            return self.role in ("owner", "admin")
        return self.role == "admin"

    @property
    def can_system_admin(self) -> bool:
        return self.is_system_admin

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

