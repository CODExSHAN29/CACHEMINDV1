import asyncio
import logging
from typing import AsyncIterator, List, Optional
from fastapi import HTTPException, status
import httpx

from backend.app.config import settings
from backend.normalization.models import NormalizedInferenceRequest
from backend.providers.base import ProviderError
from backend.providers.registry import ProviderRegistry, get_provider_registry
from backend.resilience.circuit_breaker import (
    CircuitBreakerRegistry,
    get_circuit_breaker_registry,
)
from backend.routing.models import (
    ProviderTarget,
    RoutingPlan,
    RoutingResult,
    StreamingRoutingResult,
)

logger = logging.getLogger(__name__)


def is_plain_text_compatible(request: NormalizedInferenceRequest) -> bool:
    """
    Determines whether a normalized request is strictly plain-text compatible.
    Denies cross-provider fallback if tools, tool_choice, provider options,
    structured output (response_format), or multimodal payloads are present.
    """
    if request.tools:
        return False
    if request.tool_choice is not None:
        return False
    if request.provider_options:
        return False
    if request.response_format:
        return False
    if request.attachment_hashes:
        return False

    for msg in request.messages:
        if msg.role in ("tool", "function"):
            return False
        if msg.tool_calls:
            return False
        if msg.tool_call_id is not None:
            return False
        if isinstance(msg.content, list):
            for part in msg.content:
                if isinstance(part, dict):
                    if part.get("type") != "text":
                        return False
                elif not isinstance(part, str):
                    return False

    return True


class RoutingEngine:
    """
    Intelligent Upstream Routing Engine.
    Executes model resolution, circuit breaker health checks, and automatic
    multi-provider fallback traversal on rate limits (429), outages (5xx), and timeouts.
    """

    def __init__(
        self,
        provider_registry: Optional[ProviderRegistry] = None,
        circuit_registry: Optional[CircuitBreakerRegistry] = None,
    ) -> None:
        self.provider_registry = provider_registry or get_provider_registry()
        self.circuit_registry = circuit_registry or get_circuit_breaker_registry()

    def build_routing_plan(self, request: NormalizedInferenceRequest) -> RoutingPlan:
        """
        Constructs the primary target and ordered fallback targets for a request.
        Cross-provider fallback is only allowed when explicitly permitted,
        the request is plain-text compatible, and a fallback model is configured.
        """
        primary_provider = self.provider_registry.resolve_provider_for_model(request.model)
        primary_target = ProviderTarget(provider=primary_provider, model=request.model)

        fallbacks: List[ProviderTarget] = []

        # Safe Capability-Gated Fallback
        if getattr(request, "allow_provider_fallback", False) and is_plain_text_compatible(request):
            if primary_provider == "openai":
                if settings.ANTHROPIC_FALLBACK_MODEL:
                    fallbacks.append(
                        ProviderTarget(provider="anthropic", model=settings.ANTHROPIC_FALLBACK_MODEL)
                    )
            elif primary_provider == "anthropic":
                if settings.OPENAI_FALLBACK_MODEL:
                    fallbacks.append(
                        ProviderTarget(provider="openai", model=settings.OPENAI_FALLBACK_MODEL)
                    )
            elif primary_provider == "ollama":
                if settings.OPENAI_FALLBACK_MODEL:
                    fallbacks.append(
                        ProviderTarget(provider="openai", model=settings.OPENAI_FALLBACK_MODEL)
                    )
                if settings.ANTHROPIC_FALLBACK_MODEL:
                    fallbacks.append(
                        ProviderTarget(provider="anthropic", model=settings.ANTHROPIC_FALLBACK_MODEL)
                    )

        return RoutingPlan(primary=primary_target, fallbacks=fallbacks)

    def _clone_request_for_target(
        self, request: NormalizedInferenceRequest, target: ProviderTarget
    ) -> NormalizedInferenceRequest:
        """Creates a copy of the normalized request adapted for the target model and provider."""
        data = request.model_dump()
        data["provider"] = target.provider
        data["model"] = target.model
        return NormalizedInferenceRequest(**data)

    def _is_retryable_error(self, exc: Exception) -> bool:
        """Determines whether an exception warrants attempting a fallback provider."""
        if isinstance(exc, ProviderError):
            return exc.retryable
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException, httpx.RequestError)):
            return True
        if isinstance(exc, HTTPException):
            return exc.status_code in (429, 500, 502, 503, 504)
        return False

    async def execute(
        self,
        request: NormalizedInferenceRequest,
        plan: Optional[RoutingPlan] = None,
    ) -> RoutingResult:
        """
        Executes a non-streaming chat completion request with automatic circuit-breaker
        validation and fallback chaining.
        """
        if plan is None:
            plan = self.build_routing_plan(request)

        errors_encountered: List[str] = []

        for hop_index, target in enumerate(plan.all_targets):
            breaker_key = f"{target.provider}:{target.model}"
            breaker = self.circuit_registry.get_breaker(breaker_key)

            # 1. Circuit Breaker Fast-Fail Check
            if not await breaker.can_execute():
                msg = f"Circuit breaker OPEN for target '{breaker_key}' (skipping to next fallback)"
                logger.warning(msg)
                errors_encountered.append(msg)
                continue

            provider = self.provider_registry.get(target.provider)
            if provider is None:
                msg = f"Provider '{target.provider}' not found in registry"
                logger.warning(msg)
                errors_encountered.append(msg)
                continue

            target_req = self._clone_request_for_target(request, target)

            # 2. Attempt Provider Invocation
            try:
                logger.info(
                    "Routing request to provider='%s' model='%s' (hop=%d)",
                    target.provider,
                    target.model,
                    hop_index,
                )
                response = await provider.chat_completion(target_req)
                await breaker.record_success()

                return RoutingResult(
                    response=response,
                    provider_used=target.provider,
                    model_used=target.model,
                    fallback_hops=hop_index,
                    errors_encountered=errors_encountered,
                )

            except Exception as exc:
                await breaker.record_failure()
                err_msg = f"Provider '{target.provider}' failed on model '{target.model}': {str(exc)}"
                logger.warning(err_msg)
                errors_encountered.append(err_msg)

                if not self._is_retryable_error(exc) and hop_index == 0:
                    raise exc

                continue

        # All targets exhausted
        logger.error(
            "All routing targets exhausted for model='%s'. Errors: %s",
            request.model,
            errors_encountered,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"All upstream providers in fallback chain failed: {'; '.join(errors_encountered)}",
        )

    async def execute_stream(
        self,
        request: NormalizedInferenceRequest,
        plan: Optional[RoutingPlan] = None,
    ) -> StreamingRoutingResult:
        """
        Executes a streaming chat completion request with automatic circuit-breaker
        validation and fallback chaining on initial connection failure.
        """
        if plan is None:
            plan = self.build_routing_plan(request)

        errors_encountered: List[str] = []

        for hop_index, target in enumerate(plan.all_targets):
            breaker_key = f"{target.provider}:{target.model}"
            breaker = self.circuit_registry.get_breaker(breaker_key)

            if not await breaker.can_execute():
                msg = f"Circuit breaker OPEN for streaming target '{breaker_key}'"
                logger.warning(msg)
                errors_encountered.append(msg)
                continue

            provider = self.provider_registry.get(target.provider)
            if provider is None:
                msg = f"Provider '{target.provider}' not found in registry"
                logger.warning(msg)
                errors_encountered.append(msg)
                continue

            target_req = self._clone_request_for_target(request, target)

            try:
                # Test initial connection / stream acquisition
                stream_iter = provider.chat_completion_stream(target_req)

                # To guarantee the stream didn't fail immediately on initialization,
                # we pre-fetch the first chunk safely
                first_chunk: Optional[str] = None
                try:
                    first_chunk = await stream_iter.__anext__()
                except StopAsyncIteration:
                    first_chunk = None

                await breaker.record_success()

                async def stream_wrapper(
                    initial_chunk: Optional[str],
                    it: AsyncIterator[str],
                    cb=breaker,
                ) -> AsyncIterator[str]:
                    try:
                        if initial_chunk is not None:
                            yield initial_chunk
                        async for chunk in it:
                            yield chunk
                    except Exception as stream_exc:
                        await cb.record_failure()
                        logger.error("Error during active stream execution: %s", stream_exc)
                        raise

                return StreamingRoutingResult(
                    stream=stream_wrapper(first_chunk, stream_iter),
                    provider_used=target.provider,
                    model_used=target.model,
                    fallback_hops=hop_index,
                    errors_encountered=errors_encountered,
                )

            except Exception as exc:
                await breaker.record_failure()
                err_msg = f"Streaming provider '{target.provider}' failed to start: {str(exc)}"
                logger.warning(err_msg)
                errors_encountered.append(err_msg)

                if not self._is_retryable_error(exc) and hop_index == 0:
                    raise exc

                continue

        logger.error(
            "All streaming routing targets exhausted for model='%s'. Errors: %s",
            request.model,
            errors_encountered,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"All upstream streaming providers in fallback chain failed: {'; '.join(errors_encountered)}",
        )


_routing_engine_instance: Optional[RoutingEngine] = None


def get_routing_engine() -> RoutingEngine:
    global _routing_engine_instance
    if _routing_engine_instance is None:
        _routing_engine_instance = RoutingEngine()
    return _routing_engine_instance


def set_routing_engine(engine: RoutingEngine) -> None:
    global _routing_engine_instance
    _routing_engine_instance = engine
