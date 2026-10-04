import logging
import time
import uuid
from typing import Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.auth.identity import AuthenticatedIdentity
from backend.caching.backend import ExactCacheBackend
from backend.caching.coalescer import RequestCoalescer, get_request_coalescer
from backend.caching.factory import get_cache_backend
from backend.caching.fingerprint import compute_exact_request_hash, compute_scope_hash
from backend.caching.models import CachedResponse
from backend.inference.models import InferenceResult
from backend.metrics.collector import MetricsCollector, get_metrics_collector
from backend.normalization.models import NormalizedInferenceRequest, NormalizedMessage
from backend.normalization.openai_adapter import OpenAIAdapter
from backend.providers.base import ProviderError
from backend.routing.engine import (
    InvalidFallbackConfigurationError,
    RoutingEngine,
    get_routing_engine,
)
from backend.semantic.factory import SemanticCacheService, get_semantic_cache_service
from backend.semantic.policy import evaluate_semantic_eligibility
from backend.streaming.accumulator import StreamAccumulator
from backend.streaming.sse import create_cached_stream_generator
from backend.telemetry.service import TelemetryService

logger = logging.getLogger(__name__)


def _extract_system_and_last_user_text(
    messages: List[NormalizedMessage],
) -> Tuple[Optional[str], Optional[str]]:
    """Extracts the first system prompt and the latest user prompt text for semantic scoping."""
    system_prompt: Optional[str] = None
    last_user_text: Optional[str] = None
    for msg in messages:
        if msg.role == "system" and system_prompt is None:
            system_prompt = str(msg.content or "")
        elif msg.role == "user":
            last_user_text = str(msg.content or "")
    return system_prompt, last_user_text


class InferencePipeline:
    """
    Transport-neutral and provider-neutral inference pipeline orchestrating:
    - Authoritative exact cache identity lookups (L1)
    - Semantic vector similarity searches and Arbiter guardrails (L2)
    - Single-flight coalescing and resilient upstream routing
    - Dual L1/L2 cache backfill with fallback target isolation
    - Telemetry logging and Prometheus metrics collection
    """

    def __init__(
        self,
        cache_backend: Optional[ExactCacheBackend] = None,
        semantic_service: Optional[SemanticCacheService] = None,
        routing_engine: Optional[RoutingEngine] = None,
        coalescer: Optional[RequestCoalescer] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ) -> None:
        self._cache_backend = cache_backend
        self._semantic_service = semantic_service
        self._routing_engine = routing_engine
        self._coalescer = coalescer
        self._metrics_collector = metrics_collector

    @property
    def cache_backend(self) -> ExactCacheBackend:
        return self._cache_backend or get_cache_backend()

    @property
    def semantic_service(self) -> SemanticCacheService:
        return self._semantic_service or get_semantic_cache_service()

    @property
    def routing_engine(self) -> RoutingEngine:
        return self._routing_engine or get_routing_engine()

    @property
    def coalescer(self) -> RequestCoalescer:
        return self._coalescer or get_request_coalescer()

    @property
    def metrics_collector(self) -> MetricsCollector:
        return self._metrics_collector or get_metrics_collector()

    async def execute(
        self,
        norm_req: NormalizedInferenceRequest,
        identity: AuthenticatedIdentity,
        db: AsyncSession,
        raw_requested_model: Optional[str] = None,
        request_id: Optional[str] = None,
        gateway_start_ns: Optional[int] = None,
    ) -> InferenceResult:
        """Executes the full inference pipeline returning a transport-neutral InferenceResult."""
        if gateway_start_ns is None:
            gateway_start_ns = time.perf_counter_ns()
        if request_id is None:
            request_id = str(uuid.uuid4())
        if raw_requested_model is None:
            raw_requested_model = norm_req.model

        # 1. Authoritative Exact Cache Identity Hash
        exact_request_hash = compute_exact_request_hash(
            tenant_id=identity.tenant_id,
            project_id=identity.project_id,
            provider=norm_req.provider,
            model=norm_req.model,
            request=norm_req,
        )

        # 2. Extract context for semantic scoping & volatility
        system_prompt, last_user_text = _extract_system_and_last_user_text(norm_req.messages)
        scope_hash = compute_scope_hash(
            tenant_id=identity.tenant_id,
            project_id=identity.project_id,
            provider=norm_req.provider,
            model=norm_req.model,
            system_prompt=system_prompt,
            temperature=norm_req.temperature,
            namespace=norm_req.namespace,
            tags=norm_req.tags,
            top_p=norm_req.top_p,
            max_tokens=norm_req.max_tokens,
            max_completion_tokens=norm_req.max_completion_tokens,
            presence_penalty=norm_req.presence_penalty,
            frequency_penalty=norm_req.frequency_penalty,
            seed=norm_req.seed,
            stop=norm_req.stop,
            response_format=norm_req.response_format,
            tools=norm_req.tools,
            tool_choice=norm_req.tool_choice,
        )

        # 3. L1 EXACT CACHE LOOKUP
        coalesce_key = f"{identity.tenant_id}:{identity.project_id}:{exact_request_hash}"
        cache_lookup_start_ns = time.perf_counter_ns()
        cached = await self.cache_backend.get(identity.project_id, exact_request_hash)
        exact_cache_lookup_ms = (time.perf_counter_ns() - cache_lookup_start_ns) / 1_000_000

        if cached is not None:
            was_coalesced = self.coalescer.is_recent(coalesce_key)
            await self.cache_backend.increment_hit(identity.project_id, exact_request_hash)
            response_payload = OpenAIAdapter.format_cached_response(
                cached.response_payload,
                request_id,
                norm_req.model,
            )

            usage = response_payload.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            gateway_latency_ms = (time.perf_counter_ns() - gateway_start_ns) / 1_000_000

            await TelemetryService.record_request_log(
                db=db,
                request_id=request_id,
                tenant_id=identity.tenant_id,
                project_id=identity.project_id,
                provider=norm_req.provider,
                requested_model=raw_requested_model,
                actual_model=norm_req.model,
                cache_status="EXACT_HIT",
                exact_request_hash=exact_request_hash,
                gateway_latency_ms=gateway_latency_ms,
                upstream_latency_ms=None,
                exact_cache_lookup_ms=exact_cache_lookup_ms,
                upstream_called=False,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                similarity_score=None,
                guardrail_status=None,
                guardrail_failed_check=None,
            )

            self.metrics_collector.record_request(
                tenant_id=identity.tenant_id,
                provider=norm_req.provider,
                model=norm_req.model,
                cache_status="EXACT_HIT",
                gateway_latency_ms=gateway_latency_ms,
                upstream_latency_ms=0.0,
                cache_lookup_ms=exact_cache_lookup_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            headers = {
                "X-CacheMind-Status": "EXACT_HIT",
                "X-CacheMind-Cache": "EXACT_HIT",
                "X-CacheMind-Request-ID": request_id,
                "X-CacheMind-Exact-Hash": exact_request_hash,
                "X-CacheMind-Gateway-Latency-Ms": f"{gateway_latency_ms:.3f}",
                "X-CacheMind-Lookup-Ms": f"{exact_cache_lookup_ms:.3f}",
                "X-CacheMind-Provider": norm_req.provider,
                "X-CacheMind-Model": norm_req.model,
                "X-CacheMind-Fallback-Hops": "0",
                "X-CacheMind-Coalesced": "true" if was_coalesced else "false",
            }

            if norm_req.stream:
                stream_gen = create_cached_stream_generator(response_payload, request_id, norm_req.model)
                return InferenceResult(
                    request_id=request_id,
                    cache_status="EXACT_HIT",
                    provider=norm_req.provider,
                    model=norm_req.model,
                    exact_request_hash=exact_request_hash,
                    gateway_latency_ms=gateway_latency_ms,
                    exact_cache_lookup_ms=exact_cache_lookup_ms,
                    headers=headers,
                    stream_generator=stream_gen,
                    is_stream=True,
                    was_coalesced=was_coalesced,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    scope_hash=scope_hash,
                )

            return InferenceResult(
                request_id=request_id,
                cache_status="EXACT_HIT",
                provider=norm_req.provider,
                model=norm_req.model,
                exact_request_hash=exact_request_hash,
                gateway_latency_ms=gateway_latency_ms,
                exact_cache_lookup_ms=exact_cache_lookup_ms,
                headers=headers,
                response_body=response_payload,
                is_stream=False,
                was_coalesced=was_coalesced,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                scope_hash=scope_hash,
            )

        # 4. L2 SEMANTIC VECTOR SEARCH (Opt-in and fail-closed)
        query_vector: Optional[List[float]] = None
        coalesce_key = f"{identity.tenant_id}:{identity.project_id}:{exact_request_hash}"

        if (
            settings.SEMANTIC_CACHE_MODE == "safe"
            and last_user_text
            and not self.coalescer.is_in_flight(coalesce_key)
        ):
            eligibility = evaluate_semantic_eligibility(norm_req)
            if eligibility.eligible:
                try:
                    query_vector = await self.semantic_service.embedding_engine.embed(last_user_text)
                    candidates = await self.semantic_service.backend.search(
                        query_vector=query_vector,
                        scope_hash=scope_hash,
                        top_k=5,
                        similarity_threshold=settings.VECTOR_SIMILARITY_THRESHOLD,
                    )

                    for cand in candidates:
                        cand_payload = cand.response_payload
                        cand_text = cand_payload.get("__cachemind_input_text__", "")
                        cand_sys_prompt = cand_payload.get("__cachemind_system_prompt__", None)

                        decision = await self.semantic_service.arbiter.evaluate(
                            incoming_text=last_user_text,
                            candidate_text=cand_text or last_user_text,
                            incoming_system_prompt=system_prompt,
                            candidate_system_prompt=cand_sys_prompt or system_prompt,
                        )

                        if decision.passed:
                            cleaned_payload = {
                                k: v for k, v in cand_payload.items() if not k.startswith("__cachemind_")
                            }
                            response_body = OpenAIAdapter.format_cached_response(
                                cleaned_payload,
                                request_id,
                                raw_requested_model,
                            )

                            gateway_latency_ms = (time.perf_counter_ns() - gateway_start_ns) / 1_000_000
                            usage = response_body.get("usage", {})
                            input_tokens = usage.get("prompt_tokens")
                            output_tokens = usage.get("completion_tokens")

                            await TelemetryService.record_request_log(
                                db=db,
                                request_id=request_id,
                                tenant_id=identity.tenant_id,
                                project_id=identity.project_id,
                                provider=norm_req.provider,
                                requested_model=raw_requested_model,
                                actual_model=norm_req.model,
                                cache_status="L2_HIT",
                                exact_request_hash=exact_request_hash,
                                gateway_latency_ms=gateway_latency_ms,
                                upstream_latency_ms=None,
                                exact_cache_lookup_ms=exact_cache_lookup_ms,
                                upstream_called=False,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                similarity_score=cand.similarity,
                                guardrail_status=True,
                                guardrail_failed_check=None,
                            )

                            self.metrics_collector.record_request(
                                tenant_id=identity.tenant_id,
                                provider=norm_req.provider,
                                model=norm_req.model,
                                cache_status="L2_HIT",
                                gateway_latency_ms=gateway_latency_ms,
                                upstream_latency_ms=None,
                                cache_lookup_ms=exact_cache_lookup_ms,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                            )

                            headers = {
                                "X-CacheMind-Status": "L2_HIT",
                                "X-CacheMind-Cache": "L2_HIT",
                                "X-CacheMind-Request-ID": request_id,
                                "X-CacheMind-Exact-Hash": exact_request_hash,
                                "X-CacheMind-Similarity": f"{cand.similarity:.4f}",
                                "X-CacheMind-Gateway-Latency-Ms": f"{gateway_latency_ms:.3f}",
                                "X-CacheMind-Lookup-Ms": f"{exact_cache_lookup_ms:.3f}",
                                "X-CacheMind-Provider": norm_req.provider,
                                "X-CacheMind-Model": norm_req.model,
                                "X-CacheMind-Fallback-Hops": "0",
                            }

                            if norm_req.stream:
                                stream_gen = create_cached_stream_generator(
                                    cached_payload=cleaned_payload,
                                    request_id=request_id,
                                    model=raw_requested_model,
                                )
                                return InferenceResult(
                                    request_id=request_id,
                                    cache_status="L2_HIT",
                                    provider=norm_req.provider,
                                    model=norm_req.model,
                                    exact_request_hash=exact_request_hash,
                                    gateway_latency_ms=gateway_latency_ms,
                                    exact_cache_lookup_ms=exact_cache_lookup_ms,
                                    headers=headers,
                                    stream_generator=stream_gen,
                                    is_stream=True,
                                    similarity_score=cand.similarity,
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                    scope_hash=scope_hash,
                                )

                            return InferenceResult(
                                request_id=request_id,
                                cache_status="L2_HIT",
                                provider=norm_req.provider,
                                model=norm_req.model,
                                exact_request_hash=exact_request_hash,
                                gateway_latency_ms=gateway_latency_ms,
                                exact_cache_lookup_ms=exact_cache_lookup_ms,
                                headers=headers,
                                response_body=response_body,
                                is_stream=False,
                                similarity_score=cand.similarity,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                scope_hash=scope_hash,
                            )
                except Exception as exc:
                    logger.warning("L2 semantic cache lookup failed for request %s: %s", request_id, exc)
                    self.metrics_collector.record_error(
                        error_type="semantic_cache_lookup_error",
                        tenant_id=identity.tenant_id,
                    )

        # 5. CACHE MISS -> RESILIENT ROUTING PATHWAYS

        # 5a. Streaming Cache Miss Pathway
        if norm_req.stream:
            try:
                streaming_result = await self.routing_engine.execute_stream(norm_req)

                # Derive executed fallback target hashes if routing changed provider/model
                if streaming_result.provider_used != norm_req.provider or streaming_result.model_used != norm_req.model:
                    backfill_norm_req = norm_req.model_copy(
                        update={"provider": streaming_result.provider_used, "model": streaming_result.model_used}
                    )
                    streaming_backfill_exact_hash = compute_exact_request_hash(
                        tenant_id=identity.tenant_id,
                        project_id=identity.project_id,
                        provider=streaming_result.provider_used,
                        model=streaming_result.model_used,
                        request=backfill_norm_req,
                    )
                    streaming_backfill_scope_hash = compute_scope_hash(
                        tenant_id=identity.tenant_id,
                        project_id=identity.project_id,
                        provider=streaming_result.provider_used,
                        model=streaming_result.model_used,
                        system_prompt=system_prompt,
                        temperature=norm_req.temperature,
                        namespace=norm_req.namespace,
                        tags=norm_req.tags,
                        top_p=norm_req.top_p,
                        max_tokens=norm_req.max_tokens,
                        max_completion_tokens=norm_req.max_completion_tokens,
                        presence_penalty=norm_req.presence_penalty,
                        frequency_penalty=norm_req.frequency_penalty,
                        seed=norm_req.seed,
                        stop=norm_req.stop,
                        response_format=norm_req.response_format,
                        tools=norm_req.tools,
                        tool_choice=norm_req.tool_choice,
                    )
                else:
                    streaming_backfill_exact_hash = exact_request_hash
                    streaming_backfill_scope_hash = scope_hash

                accumulator = StreamAccumulator(
                    upstream_stream=streaming_result.stream,
                    request_id=request_id,
                    identity=identity,
                    norm_req=norm_req,
                    exact_request_hash=exact_request_hash,
                    scope_hash=scope_hash,
                    last_user_text=last_user_text or "",
                    system_prompt=system_prompt,
                    gateway_start_ns=gateway_start_ns,
                    exact_cache_lookup_ms=exact_cache_lookup_ms,
                    db=db,
                    provider_used=streaming_result.provider_used,
                    model_used=streaming_result.model_used,
                    raw_requested_model=raw_requested_model,
                    fallback_hops=streaming_result.fallback_hops,
                    backfill_exact_hash=streaming_backfill_exact_hash,
                    backfill_scope_hash=streaming_backfill_scope_hash,
                )

                headers = {
                    "X-CacheMind-Status": "MISS",
                    "X-CacheMind-Cache": "MISS",
                    "X-CacheMind-Request-ID": request_id,
                    "X-CacheMind-Exact-Hash": streaming_backfill_exact_hash,
                    "X-CacheMind-Lookup-Ms": f"{exact_cache_lookup_ms:.3f}",
                    "X-CacheMind-Provider": streaming_result.provider_used,
                    "X-CacheMind-Model": streaming_result.model_used,
                    "X-CacheMind-Fallback-Hops": str(streaming_result.fallback_hops),
                }

                return InferenceResult(
                    request_id=request_id,
                    cache_status="MISS",
                    provider=streaming_result.provider_used,
                    model=streaming_result.model_used,
                    exact_request_hash=streaming_backfill_exact_hash,
                    gateway_latency_ms=0.0,
                    exact_cache_lookup_ms=exact_cache_lookup_ms,
                    headers=headers,
                    stream_generator=accumulator,
                    is_stream=True,
                    fallback_hops=streaming_result.fallback_hops,
                    scope_hash=streaming_backfill_scope_hash,
                )
            except ProviderError as pe:
                gateway_latency_ms = (time.perf_counter_ns() - gateway_start_ns) / 1_000_000
                await TelemetryService.record_request_log(
                    db=db,
                    request_id=request_id,
                    tenant_id=identity.tenant_id,
                    project_id=identity.project_id,
                    provider=norm_req.provider,
                    requested_model=raw_requested_model,
                    actual_model=norm_req.model,
                    cache_status="ERROR",
                    exact_request_hash=exact_request_hash,
                    gateway_latency_ms=gateway_latency_ms,
                    upstream_latency_ms=None,
                    exact_cache_lookup_ms=exact_cache_lookup_ms,
                    upstream_called=True,
                )
                raise
            except InvalidFallbackConfigurationError:
                gateway_latency_ms = (time.perf_counter_ns() - gateway_start_ns) / 1_000_000
                await TelemetryService.record_request_log(
                    db=db,
                    request_id=request_id,
                    tenant_id=identity.tenant_id,
                    project_id=identity.project_id,
                    provider=norm_req.provider,
                    requested_model=raw_requested_model,
                    actual_model=norm_req.model,
                    cache_status="ERROR",
                    exact_request_hash=exact_request_hash,
                    gateway_latency_ms=gateway_latency_ms,
                    upstream_latency_ms=None,
                    exact_cache_lookup_ms=exact_cache_lookup_ms,
                    upstream_called=False,
                )
                raise
            except Exception:
                gateway_latency_ms = (time.perf_counter_ns() - gateway_start_ns) / 1_000_000
                await TelemetryService.record_request_log(
                    db=db,
                    request_id=request_id,
                    tenant_id=identity.tenant_id,
                    project_id=identity.project_id,
                    provider=norm_req.provider,
                    requested_model=raw_requested_model,
                    actual_model=norm_req.model,
                    cache_status="ERROR",
                    exact_request_hash=exact_request_hash,
                    gateway_latency_ms=gateway_latency_ms,
                    upstream_latency_ms=None,
                    exact_cache_lookup_ms=exact_cache_lookup_ms,
                    upstream_called=True,
                )
                raise

        # 5b. Non-streaming Cache Miss Pathway with Single-Flight Coalescing
        upstream_start_ns = time.perf_counter_ns()
        try:
            routing_result, was_coalesced = await self.coalescer.do(
                coalesce_key,
                lambda: self.routing_engine.execute(norm_req),
            )
            provider_resp = routing_result.response
            upstream_latency_ms = (time.perf_counter_ns() - upstream_start_ns) / 1_000_000
        except ProviderError as pe:
            gateway_latency_ms = (time.perf_counter_ns() - gateway_start_ns) / 1_000_000
            await TelemetryService.record_request_log(
                db=db,
                request_id=request_id,
                tenant_id=identity.tenant_id,
                project_id=identity.project_id,
                provider=norm_req.provider,
                requested_model=raw_requested_model,
                actual_model=norm_req.model,
                cache_status="ERROR",
                exact_request_hash=exact_request_hash,
                gateway_latency_ms=gateway_latency_ms,
                upstream_latency_ms=(time.perf_counter_ns() - upstream_start_ns) / 1_000_000,
                exact_cache_lookup_ms=exact_cache_lookup_ms,
                upstream_called=True,
            )
            raise
        except InvalidFallbackConfigurationError:
            gateway_latency_ms = (time.perf_counter_ns() - gateway_start_ns) / 1_000_000
            await TelemetryService.record_request_log(
                db=db,
                request_id=request_id,
                tenant_id=identity.tenant_id,
                project_id=identity.project_id,
                provider=norm_req.provider,
                requested_model=raw_requested_model,
                actual_model=norm_req.model,
                cache_status="ERROR",
                exact_request_hash=exact_request_hash,
                gateway_latency_ms=gateway_latency_ms,
                upstream_latency_ms=(time.perf_counter_ns() - upstream_start_ns) / 1_000_000,
                exact_cache_lookup_ms=exact_cache_lookup_ms,
                upstream_called=False,
            )
            raise
        except Exception:
            gateway_latency_ms = (time.perf_counter_ns() - gateway_start_ns) / 1_000_000
            await TelemetryService.record_request_log(
                db=db,
                request_id=request_id,
                tenant_id=identity.tenant_id,
                project_id=identity.project_id,
                provider=norm_req.provider,
                requested_model=raw_requested_model,
                actual_model=norm_req.model,
                cache_status="ERROR",
                exact_request_hash=exact_request_hash,
                gateway_latency_ms=gateway_latency_ms,
                upstream_latency_ms=(time.perf_counter_ns() - upstream_start_ns) / 1_000_000,
                exact_cache_lookup_ms=exact_cache_lookup_ms,
                upstream_called=True,
            )
            raise

        # 6. DUAL BACKFILL: Populate L1 Exact Cache + L2 Semantic Cache on Success
        ttl_seconds = settings.DEFAULT_CACHE_TTL_SECONDS
        if last_user_text:
            try:
                volatility_info = await self.semantic_service.volatility_engine.classify(last_user_text)
                ttl_seconds = volatility_info.ttl_seconds
            except Exception:
                ttl_seconds = settings.DEFAULT_CACHE_TTL_SECONDS

        # Derive Backfill Exact Hash & Scope Hash under Executed Target
        if routing_result.provider_used != norm_req.provider or routing_result.model_used != norm_req.model:
            backfill_norm_req = norm_req.model_copy(
                update={"provider": routing_result.provider_used, "model": routing_result.model_used}
            )
            backfill_exact_hash = compute_exact_request_hash(
                tenant_id=identity.tenant_id,
                project_id=identity.project_id,
                provider=routing_result.provider_used,
                model=routing_result.model_used,
                request=backfill_norm_req,
            )
            backfill_scope_hash = compute_scope_hash(
                tenant_id=identity.tenant_id,
                project_id=identity.project_id,
                provider=routing_result.provider_used,
                model=routing_result.model_used,
                system_prompt=system_prompt,
                temperature=norm_req.temperature,
                namespace=norm_req.namespace,
                tags=norm_req.tags,
                top_p=norm_req.top_p,
                max_tokens=norm_req.max_tokens,
                max_completion_tokens=norm_req.max_completion_tokens,
                presence_penalty=norm_req.presence_penalty,
                frequency_penalty=norm_req.frequency_penalty,
                seed=norm_req.seed,
                stop=norm_req.stop,
                response_format=norm_req.response_format,
                tools=norm_req.tools,
                tool_choice=norm_req.tool_choice,
            )
        else:
            backfill_exact_hash = exact_request_hash
            backfill_scope_hash = scope_hash

        # 6a. L1 Exact Cache Set
        cached_entry = CachedResponse(
            exact_request_hash=backfill_exact_hash,
            response_payload=provider_resp.raw_response,
            provider=routing_result.provider_used,
            model=routing_result.model_used,
            ttl_seconds=ttl_seconds,
            namespace=norm_req.namespace,
            tags=norm_req.tags,
        )
        await self.cache_backend.set(
            identity.project_id,
            backfill_exact_hash,
            cached_entry,
            ttl_seconds,
        )

        # 6b. L2 Semantic Vector Backend Insert (Opt-in and fail-closed)
        if settings.SEMANTIC_CACHE_MODE == "safe" and last_user_text:
            eligibility = evaluate_semantic_eligibility(norm_req)
            if eligibility.eligible:
                try:
                    if query_vector is None:
                        query_vector = await self.semantic_service.embedding_engine.embed(last_user_text)

                    semantic_payload = dict(provider_resp.raw_response)
                    semantic_payload["__cachemind_input_text__"] = last_user_text
                    semantic_payload["__cachemind_system_prompt__"] = system_prompt

                    await self.semantic_service.backend.insert(
                        scope_hash=backfill_scope_hash,
                        exact_request_hash=backfill_exact_hash,
                        vector=query_vector,
                        response_payload=semantic_payload,
                        created_at=time.time(),
                        input_text=last_user_text,
                        system_prompt=system_prompt,
                        provider=routing_result.provider_used,
                        model=routing_result.model_used,
                        ttl_seconds=ttl_seconds,
                        tenant_id=identity.tenant_id,
                        project_id=identity.project_id,
                        namespace=norm_req.namespace,
                        tags=norm_req.tags,
                    )
                except Exception as exc:
                    logger.warning("L2 semantic cache insertion failed for request %s: %s", request_id, exc)
                    self.metrics_collector.record_error(
                        error_type="semantic_cache_insert_error",
                        tenant_id=identity.tenant_id,
                    )

        gateway_latency_ms = (time.perf_counter_ns() - gateway_start_ns) / 1_000_000
        effective_exact_hash = (
            backfill_exact_hash
            if (routing_result.provider_used != norm_req.provider or routing_result.model_used != norm_req.model)
            else exact_request_hash
        )

        # 7. Telemetry & Metrics Recording
        await TelemetryService.record_request_log(
            db=db,
            request_id=request_id,
            tenant_id=identity.tenant_id,
            project_id=identity.project_id,
            provider=routing_result.provider_used,
            requested_model=raw_requested_model,
            actual_model=routing_result.model_used,
            cache_status="MISS",
            exact_request_hash=effective_exact_hash,
            gateway_latency_ms=gateway_latency_ms,
            upstream_latency_ms=upstream_latency_ms,
            exact_cache_lookup_ms=exact_cache_lookup_ms,
            upstream_called=True,
            input_tokens=provider_resp.input_tokens,
            output_tokens=provider_resp.output_tokens,
            similarity_score=None,
            guardrail_status=None,
            guardrail_failed_check=None,
        )

        self.metrics_collector.record_request(
            tenant_id=identity.tenant_id,
            provider=routing_result.provider_used,
            model=routing_result.model_used,
            cache_status="MISS",
            gateway_latency_ms=gateway_latency_ms,
            upstream_latency_ms=upstream_latency_ms,
            cache_lookup_ms=exact_cache_lookup_ms,
            input_tokens=provider_resp.input_tokens,
            output_tokens=provider_resp.output_tokens,
        )

        headers = {
            "X-CacheMind-Status": "MISS",
            "X-CacheMind-Cache": "MISS",
            "X-CacheMind-Request-ID": request_id,
            "X-CacheMind-Exact-Hash": effective_exact_hash,
            "X-CacheMind-Gateway-Latency-Ms": f"{gateway_latency_ms:.3f}",
            "X-CacheMind-Lookup-Ms": f"{exact_cache_lookup_ms:.3f}",
            "X-CacheMind-Upstream-Ms": f"{upstream_latency_ms:.3f}",
            "X-CacheMind-Provider": routing_result.provider_used,
            "X-CacheMind-Model": routing_result.model_used,
            "X-CacheMind-Fallback-Hops": str(routing_result.fallback_hops),
            "X-CacheMind-Coalesced": "true" if was_coalesced else "false",
        }

        return InferenceResult(
            request_id=request_id,
            cache_status="MISS",
            provider=routing_result.provider_used,
            model=routing_result.model_used,
            exact_request_hash=effective_exact_hash,
            gateway_latency_ms=gateway_latency_ms,
            exact_cache_lookup_ms=exact_cache_lookup_ms,
            upstream_latency_ms=upstream_latency_ms,
            headers=headers,
            response_body=provider_resp.raw_response,
            is_stream=False,
            fallback_hops=routing_result.fallback_hops,
            was_coalesced=was_coalesced,
            input_tokens=provider_resp.input_tokens,
            output_tokens=provider_resp.output_tokens,
            scope_hash=backfill_scope_hash,
        )


_pipeline_instance: Optional[InferencePipeline] = None


def get_inference_pipeline() -> InferencePipeline:
    """Returns the singleton InferencePipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = InferencePipeline()
    return _pipeline_instance


def set_inference_pipeline(pipeline: Optional[InferencePipeline]) -> None:
    """Explicitly sets or resets the singleton InferencePipeline instance (used in tests)."""
    global _pipeline_instance
    _pipeline_instance = pipeline
