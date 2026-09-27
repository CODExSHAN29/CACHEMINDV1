from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CachedResponse(BaseModel):
    """
    Authoritative cached payload structure stored in exact cache backend.
    """
    exact_request_hash: str = ""
    response_payload: Dict[str, Any] = Field(default_factory=dict)
    provider: str = "openai"
    model: str = "gpt-4o"
    id: Optional[str] = None
    content: Optional[str] = None
    created: Optional[int] = None
    cached_at: Optional[float] = None
    ttl: Optional[int] = None
    created_at: float = Field(default_factory=time.time)
    ttl_seconds: int = 86400
    hit_count: int = 0
    namespace: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def is_expired(self) -> bool:
        created_time = self.cached_at if self.cached_at is not None else self.created_at
        ttl_val = self.ttl if self.ttl is not None else self.ttl_seconds
        return (time.time() - created_time) > ttl_val
