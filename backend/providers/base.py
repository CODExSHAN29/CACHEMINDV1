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


def make_safe_provider_message(provider: str, kind: ProviderErrorKind, status_code: Optional[int] = None) -> str:
    """
    Generates a sanitized, deterministic error message without raw upstream payloads.
    Prevents leaking internal prompt data, API credentials, or organizational identifiers.
    """
    prov_name = provider.capitalize() if provider else "Upstream"
    messages = {
        ProviderErrorKind.AUTHENTICATION_ERROR: f"Authentication failed with {provider} upstream.",
        ProviderErrorKind.PERMISSION_DENIED: f"Access denied by {provider} upstream.",
        ProviderErrorKind.NOT_FOUND: f"Requested model or resource not found on {provider} upstream.",
        ProviderErrorKind.INVALID_REQUEST: f"Invalid request sent to {provider} upstream.",
        ProviderErrorKind.RATE_LIMIT_EXCEEDED: f"Rate limit exceeded on {provider} upstream.",
        ProviderErrorKind.UPSTREAM_UNAVAILABLE: f"{prov_name} upstream service is temporarily unavailable.",
        ProviderErrorKind.INTERNAL_SERVER_ERROR: f"{prov_name} upstream encountered an internal server error.",
        ProviderErrorKind.TIMEOUT: f"Request to {provider} upstream timed out.",
        ProviderErrorKind.NETWORK_ERROR: f"Network connection error communicating with {provider} upstream.",
        ProviderErrorKind.CONTENT_FILTER: f"Request was filtered by {provider} upstream content moderation policy.",
        ProviderErrorKind.CONTEXT_LENGTH_EXCEEDED: f"Request exceeded maximum context length for {provider} model.",
        ProviderErrorKind.CONFIGURATION_ERROR: f"{prov_name} upstream is not properly configured.",
        ProviderErrorKind.UNKNOWN: f"An unexpected error occurred with {provider} upstream.",
    }
    return messages.get(kind, f"An error occurred communicating with {provider} upstream.")


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
