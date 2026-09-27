from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Protocol, runtime_checkable

from backend.normalization.models import NormalizedInferenceRequest


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
