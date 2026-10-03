import logging
from typing import TYPE_CHECKING, AsyncIterator, List, Optional
from fastapi import HTTPException, status

from backend.app.config import settings
from backend.normalization.models import NormalizedInferenceRequest
from backend.providers.base import ProviderError, ProviderErrorKind
from backend.resilience.circuit_breaker import (
    CircuitBreakerRegistry,
    get_circuit_breaker_registry,
)
from backend.routing.model_catalog import UnknownModelError, resolve_model
from backend.routing.models import (
    ProviderTarget,
    RoutingPlan,
    RoutingResult,
    StreamingRoutingResult,
)

if TYPE_CHECKING:
    from backend.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class InvalidFallbackConfigurationError(Exception):
    """Raised when configured provider fallback target is invalid or misconfigured."""
    pass


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
        provider_registry: Optional["ProviderRegistry"] = None,
        circuit_registry: Optional[CircuitBreakerRegistry] = None,
    ) -> None:
        if provider_registry is None:
            from backend.providers.registry import get_provider_registry
            self.provider_registry = get_provider_registry()
        else:
            self.provider_registry = provider_registry
        self.circuit_registry = circuit_registry or get_circuit_breaker_registry()

    def build_routing_plan(self, request: NormalizedInferenceRequest) -> RoutingPlan:
        """
        Constructs the primary target and ordered fallback targets for a request.
        Cross-provider fallback is only allowed when explicitly permitted,
        the request is plain-text compatible, and the target fallback model is validated.
        Automatic fallback only occurs between OpenAI and Anthropic.
        """
        primary_provider = self.provider_registry.resolve_provider_for_model(request.model)
        primary_target = ProviderTarget(provider=primary_provider, model=request.model)

        fallbacks: List[ProviderTarget] = []

        # Automatic fallback only between OpenAI and Anthropic for plain-text compatible requests
        if getattr(request, "allow_provider_fallback", False) and is_plain_text_compatible(request):
            target_fallback_model: Optional[str] = None
            expected_provider: Optional[str] = None

            if primary_provider == "openai":
                target_fallback_model = settings.ANTHROPIC_FALLBACK_MODEL
                expected_provider = "anthropic"
            elif primary_provider == "anthropic":
                target_fallback_model = settings.OPENAI_FALLBACK_MODEL
                expected_provider = "openai"

            if primary_provider in ("openai", "anthropic"):
                if not target_fallback_model:
                    raise InvalidFallbackConfigurationError(
                        f"No fallback model configured for '{primary_provider}' primary provider"
                    )

                try:
                    resolved_fallback = resolve_model(target_fallback_model)
                except UnknownModelError as exc:
                    raise InvalidFallbackConfigurationError(
                        f"Configured fallback model '{target_fallback_model}' could not be resolved in catalog"
                    ) from exc

                if resolved_fallback.provider != expected_provider:
                    raise InvalidFallbackConfigurationError(
                        f"Configured fallback model '{target_fallback_model}' resolved to provider '{resolved_fallback.provider}', expected '{expected_provider}'"
                    )

                # Capability gating
                caps = resolved_fallback.capabilities
                streaming_ok = not request.stream or caps.streaming
                has_system_msg = any(msg.role == "system" for msg in request.messages)
                system_ok = not has_system_msg or caps.system_instructions

                if streaming_ok and system_ok:
                    fallbacks.append(
                        ProviderTarget(
                            provider=expected_provider,
                            model=resolved_fallback.canonical_model,
                        )
                    )
                else:
                    logger.info(
                        "Fallback model '%s' rejected due to capability mismatch: streaming_ok=%s, system_ok=%s",
                        target_fallback_model,
                        streaming_ok,
                        system_ok,
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

    def _should_trip_circuit(self, exc: Exception) -> bool:
        """
        Determines whether an exception represents an upstream availability failure that
        should trip the provider circuit breaker. Client faults (400, 401, 403, 404,
        context length exceeded, content filter, configuration error) must NOT trip the circuit.
        Governed solely by normalized ProviderError contracts.
        """
        if isinstance(exc, ProviderError):
            if exc.kind in (
                ProviderErrorKind.UPSTREAM_UNAVAILABLE,
                ProviderErrorKind.INTERNAL_SERVER_ERROR,
                ProviderErrorKind.TIMEOUT,
                ProviderErrorKind.NETWORK_ERROR,
                ProviderErrorKind.RATE_LIMIT_EXCEEDED,
            ) or (exc.status_code and exc.status_code in (429, 500, 502, 503, 504, 529)):
                return True
        return False

    def _is_retryable_error(self, exc: Exception) -> bool:
        """
        Determines whether an exception warrants attempting a fallback provider.
        Governed solely by normalized ProviderError contracts.
        """
        return isinstance(exc, ProviderError) and exc.retryable

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
                if self._should_trip_circuit(exc):
                    await breaker.record_failure()

                if isinstance(exc, ProviderError):
                    err_msg = f"{target.provider}:{target.model} - {exc.safe_message}"
                else:
                    err_msg = f"{target.provider}:{target.model} - An unexpected upstream error occurred."

                logger.warning("Provider '%s' failed on model '%s': %s", target.provider, target.model, err_msg)
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
                        if self._should_trip_circuit(stream_exc):
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
                if self._should_trip_circuit(exc):
                    await breaker.record_failure()

                if isinstance(exc, ProviderError):
                    err_msg = f"{target.provider}:{target.model} - {exc.safe_message}"
                else:
                    err_msg = f"{target.provider}:{target.model} - An unexpected upstream error occurred."

                logger.warning("Streaming provider '%s' failed to start: %s", target.provider, err_msg)
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

