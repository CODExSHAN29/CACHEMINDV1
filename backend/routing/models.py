from dataclasses import dataclass, field
from typing import AsyncIterator, List, Optional
from backend.providers.base import ProviderResponse


@dataclass
class ProviderTarget:
    """Represents a specific target provider and model destination."""
    provider: str
    model: str


@dataclass
class RoutingPlan:
    """Represents the primary target and ordered fallback targets."""
    primary: ProviderTarget
    fallbacks: List[ProviderTarget] = field(default_factory=list)

    @property
    def all_targets(self) -> List[ProviderTarget]:
        return [self.primary] + self.fallbacks


@dataclass
class RoutingResult:
    """Encapsulates the successful upstream response along with routing telemetry."""
    response: ProviderResponse
    provider_used: str
    model_used: str
    fallback_hops: int = 0
    errors_encountered: List[str] = field(default_factory=list)


@dataclass
class StreamingRoutingResult:
    """Encapsulates an active SSE stream along with routing metadata."""
    stream: AsyncIterator[str]
    provider_used: str
    model_used: str
    fallback_hops: int = 0
    errors_encountered: List[str] = field(default_factory=list)
