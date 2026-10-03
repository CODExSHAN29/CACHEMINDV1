from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Dict, Optional, Protocol, runtime_checkable

from backend.normalization.models import NormalizedInferenceRequest


class ProviderErrorKind(str, Enum):
    AUTHENTICATION_ERROR = "authentication_error"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    INVALID_REQUEST = "invalid_request"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    INTERNAL_SERVER_ERROR = "internal_server_error"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    CONTENT_FILTER = "content_filter"
    CONTEXT_LENGTH_EXCEEDED = "context_length_exceeded"
    CONFIGURATION_ERROR = "configuration_error"
    UNKNOWN = "unknown"


class ProviderError(Exception):
    """
    Typed upstream provider error carrying status codes, retryability, and safe messages.
    Providers must raise ProviderError instead of framework exceptions (e.g. HTTPException).
    """

    def __init__(
        self,
        provider: str,
        kind: ProviderErrorKind,
        status_code: Optional[int] = None,
        provider_code: Optional[str] = None,
        retryable: bool = False,
        retry_after_seconds: Optional[float] = None,
        safe_message: str = "An error occurred communicating with the upstream provider.",
    ) -> None:
        super().__init__(safe_message)
        self.provider = provider
        self.kind = kind
        self.status_code = status_code
        self.provider_code = provider_code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.safe_message = safe_message

    def __str__(self) -> str:
        return f"ProviderError(provider={self.provider}, kind={self.kind.value}, status_code={self.status_code}, retryable={self.retryable}): {self.safe_message}"


@dataclass(frozen=True)
class ProviderResponse:
    """
    Standardized response container returned by LLM upstream providers.
    """
    raw_response: Dict[str, Any]
    input_tokens: int
    output_tokens: int
    model: str
    provider_latency_ms: float


@runtime_checkable
class BaseProvider(Protocol):
    """
    Protocol defining LLM inference provider interface.
    """

    async def chat_completion(
        self, request: NormalizedInferenceRequest
    ) -> ProviderResponse:
        """Executes chat completion request against provider."""
        ...

    async def chat_completion_stream(
        self, request: NormalizedInferenceRequest
    ) -> AsyncIterator[str]:
        """Executes streaming chat completion request yielding raw SSE chunks."""
        ...

    async def close(self) -> None:
        """Cleans up any allocated network or client resources."""
        ...
