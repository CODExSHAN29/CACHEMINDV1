import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

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
from backend.providers.base import ProviderError
from backend.routing.engine import (
    InvalidFallbackConfigurationError,
    RoutingEngine,
    RoutingResult,
    StreamingRoutingResult,
    get_routing_engine,
)
from backend.semantic.factory import SemanticCacheService, get_semantic_cache_service
from backend.semantic.policy import evaluate_semantic_eligibility
from backend.streaming.accumulator import StreamAccumulator
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

    def _derive_target_cache_identity(
        self,
        identity: AuthenticatedIdentity,
        norm_req: NormalizedInferenceRequest,
        target_provider: str,
        target_model: str,
        system_prompt: Optional[str],
        exact_request_hash: str,
        scope_hash: str,
    ) -> Tuple[str, str]:
        """Derives fallback-isolated exact and scope hashes when executed provider/model differs from request."""
        if target_provider == norm_req.provider and target_model == norm_req.model:
            return exact_request_hash, scope_hash

        backfill_norm_req = norm_req.model_copy(
            update={"provider": target_provider, "model": target_model}
        )
        backfill_exact_hash = compute_exact_request_hash(
            tenant_id=identity.tenant_id,
            project_id=identity.project_id,
            provider=target_provider,
            model=target_model,
            request=backfill_norm_req,
        )
        backfill_scope_hash = compute_scope_hash(
            tenant_id=identity.tenant_id,
            project_id=identity.project_id,
            provider=target_provider,
            model=target_model,
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
        return backfill_exact_hash, backfill_scope_hash

    async def _record_execution_error(
        self,
        db: AsyncSession,
        request_id: str,
        identity: AuthenticatedIdentity,
        norm_req: NormalizedInferenceRequest,
        raw_requested_model: str,
        exact_request_hash: str,
        gateway_start_ns: int,
        exact_cache_lookup_ms: float,
        upstream_latency_ms: Optional[float] = None,
        upstream_called: bool = True,
    ) -> None:
        """Records error telemetry in database."""
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
            upstream_latency_ms=upstream_latency_ms,
            exact_cache_lookup_ms=exact_cache_lookup_ms,
            upstream_called=upstream_called,
        )

    async def _try_exact_cache(
        self,
        identity: AuthenticatedIdentity,
        norm_req: NormalizedInferenceRequest,
        raw_requested_model: str,
        request_id: str,
        exact_request_hash: str,
        scope_hash: str,
        gateway_start_ns: int,
        db: AsyncSession,
    ) -> Tuple[Optional[InferenceResult], float]:
        """Attempts L1 exact cache lookup. Returns (InferenceResult, lookup_ms) or (None, lookup_ms)."""
        coalesce_key = f"{identity.tenant_id}:{identity.project_id}:{exact_request_hash}"
        cache_lookup_start_ns = time.perf_counter_ns()
        cached = await self.cache_backend.get(identity.project_id, exact_request_hash)
        exact_cache_lookup_ms = (time.perf_counter_ns() - cache_lookup_start_ns) / 1_000_000

        if cached is None:
            return None, exact_cache_lookup_ms

        was_coalesced = self.coalescer.is_recent(coalesce_key)
        await self.cache_backend.increment_hit(identity.project_id, exact_request_hash)

        # Restore cached ownership attribution
        actual_provider = cached.provider or norm_req.provider
        actual_model = cached.model or norm_req.model

        raw_payload = cached.response_payload or {}
        usage = raw_payload.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        gateway_latency_ms = (time.perf_counter_ns() - gateway_start_ns) / 1_000_000

        await TelemetryService.record_request_log(
            db=db,
            request_id=request_id,
            tenant_id=identity.tenant_id,
            project_id=identity.project_id,
            provider=actual_provider,
            requested_model=raw_requested_model,
            actual_model=actual_model,
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
            provider=actual_provider,
            model=actual_model,
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
            "X-CacheMind-Provider": actual_provider,
            "X-CacheMind-Model": actual_model,
            "X-CacheMind-Fallback-Hops": "0",
            "X-CacheMind-Coalesced": "true" if was_coalesced else "false",
        }

        result = InferenceResult(
            request_id=request_id,
            cache_status="EXACT_HIT",
            provider=actual_provider,
            model=actual_model,
            exact_request_hash=exact_request_hash,
            gateway_latency_ms=gateway_latency_ms,
            exact_cache_lookup_ms=exact_cache_lookup_ms,
            headers=headers,
            response_body=raw_payload,
            stream_generator=None,
            is_stream=norm_req.stream,
            was_coalesced=was_coalesced,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            scope_hash=scope_hash,
        )
        return result, exact_cache_lookup_ms

    async def _try_semantic_cache(
        self,
        identity: AuthenticatedIdentity,
        norm_req: NormalizedInferenceRequest,
        raw_requested_model: str,
        request_id: str,
        exact_request_hash: str,
        scope_hash: str,
        system_prompt: Optional[str],
        last_user_text: Optional[str],
        gateway_start_ns: int,
        exact_cache_lookup_ms: float,
        db: AsyncSession,
    ) -> Tuple[Optional[InferenceResult], Optional[List[float]]]:
        """Attempts L2 semantic cache search and Arbiter evaluation."""
        coalesce_key = f"{identity.tenant_id}:{identity.project_id}:{exact_request_hash}"
        query_vector: Optional[List[float]] = None

        if (
            settings.SEMANTIC_CACHE_MODE != "safe"
            or not last_user_text
            or self.coalescer.is_in_flight(coalesce_key)
        ):
            return None, query_vector

        eligibility = evaluate_semantic_eligibility(norm_req)
        if not eligibility.eligible:
            return None, query_vector

        try:
            query_vector = await self.semantic_service.embedding_engine.embed(last_user_text)
            candidates = await self.semantic_service.backend.search(
                query_vector=query_vector,
                scope_hash=scope_hash,
                top_k=5,
                similarity_threshold=settings.VECTOR_SIMILARITY_THRESHOLD,
            )

            for cand in candidates:
                cand_payload = cand.response_payload or {}
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
                    gateway_latency_ms = (time.perf_counter_ns() - gateway_start_ns) / 1_000_000
                    usage = cleaned_payload.get("usage", {})
                    input_tokens = usage.get("prompt_tokens")
                    output_tokens = usage.get("completion_tokens")

                    # Cached ownership from candidate or request
                    actual_provider = getattr(cand, "provider", None) or norm_req.provider
                    actual_model = getattr(cand, "model", None) or norm_req.model

                    await TelemetryService.record_request_log(
                        db=db,
                        request_id=request_id,
                        tenant_id=identity.tenant_id,
                        project_id=identity.project_id,
                        provider=actual_provider,
                        requested_model=raw_requested_model,
                        actual_model=actual_model,
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
                        provider=actual_provider,
                        model=actual_model,
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
                        "X-CacheMind-Provider": actual_provider,
                        "X-CacheMind-Model": actual_model,
                        "X-CacheMind-Fallback-Hops": "0",
                    }

                    result = InferenceResult(
                        request_id=request_id,
                        cache_status="L2_HIT",
                        provider=actual_provider,
                        model=actual_model,
                        exact_request_hash=exact_request_hash,
                        gateway_latency_ms=gateway_latency_ms,
                        exact_cache_lookup_ms=exact_cache_lookup_ms,
                        headers=headers,
                        response_body=cleaned_payload,
                        stream_generator=None,
                        is_stream=norm_req.stream,
                        similarity_score=cand.similarity,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        scope_hash=scope_hash,
                    )
                    return result, query_vector
        except Exception as exc:
            logger.warning("L2 semantic cache lookup failed for request %s: %s", request_id, exc)
            self.metrics_collector.record_error(
                error_type="semantic_cache_lookup_error",
                tenant_id=identity.tenant_id,
            )

        return None, query_vector

    async def _execute_stream_miss(
        self,
        identity: AuthenticatedIdentity,
        norm_req: NormalizedInferenceRequest,
        raw_requested_model: str,
        request_id: str,
        exact_request_hash: str,
        scope_hash: str,
        system_prompt: Optional[str],
        last_user_text: Optional[str],
        gateway_start_ns: int,
        exact_cache_lookup_ms: float,
        db: AsyncSession,
    ) -> InferenceResult:
        """Executes streaming upstream miss via RoutingEngine and StreamAccumulator."""
        try:
            streaming_result: StreamingRoutingResult = await self.routing_engine.execute_stream(norm_req)
        except ProviderError:
            await self._record_execution_error(
                db, request_id, identity, norm_req, raw_requested_model,
                exact_request_hash, gateway_start_ns, exact_cache_lookup_ms, upstream_called=True
            )
            raise
        except InvalidFallbackConfigurationError:
            await self._record_execution_error(
                db, request_id, identity, norm_req, raw_requested_model,
                exact_request_hash, gateway_start_ns, exact_cache_lookup_ms, upstream_called=False
            )
            raise
        except Exception:
            await self._record_execution_error(
                db, request_id, identity, norm_req, raw_requested_model,
                exact_request_hash, gateway_start_ns, exact_cache_lookup_ms, upstream_called=True
            )
            raise

        backfill_exact_hash, backfill_scope_hash = self._derive_target_cache_identity(
            identity=identity,
            norm_req=norm_req,
            target_provider=streaming_result.provider_used,
            target_model=streaming_result.model_used,
            system_prompt=system_prompt,
            exact_request_hash=exact_request_hash,
            scope_hash=scope_hash,
        )

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
            backfill_exact_hash=backfill_exact_hash,
            backfill_scope_hash=backfill_scope_hash,
        )

        headers = {
            "X-CacheMind-Status": "MISS",
            "X-CacheMind-Cache": "MISS",
            "X-CacheMind-Request-ID": request_id,
            "X-CacheMind-Exact-Hash": backfill_exact_hash,
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
            exact_request_hash=backfill_exact_hash,
            gateway_latency_ms=0.0,
            exact_cache_lookup_ms=exact_cache_lookup_ms,
            headers=headers,
            stream_generator=accumulator,
            is_stream=True,
            fallback_hops=streaming_result.fallback_hops,
            scope_hash=backfill_scope_hash,
        )

    async def _backfill_nonstream(
        self,
        identity: AuthenticatedIdentity,
        norm_req: NormalizedInferenceRequest,
        routing_result: RoutingResult,
        backfill_exact_hash: str,
        backfill_scope_hash: str,
        system_prompt: Optional[str],
        last_user_text: Optional[str],
        query_vector: Optional[List[float]],
        request_id: str,
    ) -> None:
        """Dual L1/L2 backfill for successful non-streaming execution."""
        ttl_seconds = settings.DEFAULT_CACHE_TTL_SECONDS
        if last_user_text:
            try:
                volatility_info = await self.semantic_service.volatility_engine.classify(last_user_text)
                ttl_seconds = volatility_info.ttl_seconds
            except Exception:
                ttl_seconds = settings.DEFAULT_CACHE_TTL_SECONDS

        # L1 Exact Cache Set
        cached_entry = CachedResponse(
            exact_request_hash=backfill_exact_hash,
            response_payload=routing_result.response.raw_response,
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

        # L2 Semantic Cache Insert
        if settings.SEMANTIC_CACHE_MODE == "safe" and last_user_text:
            eligibility = evaluate_semantic_eligibility(norm_req)
            if eligibility.eligible:
                try:
                    if query_vector is None:
                        query_vector = await self.semantic_service.embedding_engine.embed(last_user_text)

                    semantic_payload = dict(routing_result.response.raw_response)
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

    async def _execute_nonstream_miss(
        self,
        identity: AuthenticatedIdentity,
        norm_req: NormalizedInferenceRequest,
        raw_requested_model: str,
        request_id: str,
        exact_request_hash: str,
        scope_hash: str,
        system_prompt: Optional[str],
        last_user_text: Optional[str],
        query_vector: Optional[List[float]],
        gateway_start_ns: int,
        exact_cache_lookup_ms: float,
        db: AsyncSession,
    ) -> InferenceResult:
        """Executes non-streaming upstream miss with coalescing and dual backfill."""
        coalesce_key = f"{identity.tenant_id}:{identity.project_id}:{exact_request_hash}"
        upstream_start_ns = time.perf_counter_ns()

        try:
            routing_result, was_coalesced = await self.coalescer.do(
                coalesce_key,
                lambda: self.routing_engine.execute(norm_req),
            )
            provider_resp = routing_result.response
            upstream_latency_ms = (time.perf_counter_ns() - upstream_start_ns) / 1_000_000
        except ProviderError:
            await self._record_execution_error(
                db, request_id, identity, norm_req, raw_requested_model,
                exact_request_hash, gateway_start_ns, exact_cache_lookup_ms,
                upstream_latency_ms=(time.perf_counter_ns() - upstream_start_ns) / 1_000_000,
                upstream_called=True,
            )
            raise
        except InvalidFallbackConfigurationError:
            await self._record_execution_error(
                db, request_id, identity, norm_req, raw_requested_model,
                exact_request_hash, gateway_start_ns, exact_cache_lookup_ms,
                upstream_latency_ms=(time.perf_counter_ns() - upstream_start_ns) / 1_000_000,
                upstream_called=False,
            )
            raise
        except Exception:
            await self._record_execution_error(
                db, request_id, identity, norm_req, raw_requested_model,
                exact_request_hash, gateway_start_ns, exact_cache_lookup_ms,
                upstream_latency_ms=(time.perf_counter_ns() - upstream_start_ns) / 1_000_000,
                upstream_called=True,
            )
            raise

        backfill_exact_hash, backfill_scope_hash = self._derive_target_cache_identity(
            identity=identity,
            norm_req=norm_req,
            target_provider=routing_result.provider_used,
            target_model=routing_result.model_used,
            system_prompt=system_prompt,
            exact_request_hash=exact_request_hash,
            scope_hash=scope_hash,
        )

        await self._backfill_nonstream(
            identity=identity,
            norm_req=norm_req,
            routing_result=routing_result,
            backfill_exact_hash=backfill_exact_hash,
            backfill_scope_hash=backfill_scope_hash,
            system_prompt=system_prompt,
            last_user_text=last_user_text,
            query_vector=query_vector,
            request_id=request_id,
        )

        gateway_latency_ms = (time.perf_counter_ns() - gateway_start_ns) / 1_000_000

        await TelemetryService.record_request_log(
            db=db,
            request_id=request_id,
            tenant_id=identity.tenant_id,
            project_id=identity.project_id,
            provider=routing_result.provider_used,
            requested_model=raw_requested_model,
            actual_model=routing_result.model_used,
            cache_status="MISS",
            exact_request_hash=backfill_exact_hash,
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
            "X-CacheMind-Exact-Hash": backfill_exact_hash,
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
            exact_request_hash=backfill_exact_hash,
            gateway_latency_ms=gateway_latency_ms,
            exact_cache_lookup_ms=exact_cache_lookup_ms,
            upstream_latency_ms=upstream_latency_ms,
            headers=headers,
            response_body=provider_resp.raw_response,
            stream_generator=None,
            is_stream=False,
            fallback_hops=routing_result.fallback_hops,
            was_coalesced=was_coalesced,
            input_tokens=provider_resp.input_tokens,
            output_tokens=provider_resp.output_tokens,
            scope_hash=backfill_scope_hash,
        )

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

        # 2. Extract Context for Semantic Scoping & Volatility
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

        # 3. L1 Exact Cache Lookup
        exact_result, exact_cache_lookup_ms = await self._try_exact_cache(
            identity=identity,
            norm_req=norm_req,
            raw_requested_model=raw_requested_model,
            request_id=request_id,
            exact_request_hash=exact_request_hash,
            scope_hash=scope_hash,
            gateway_start_ns=gateway_start_ns,
            db=db,
        )
        if exact_result is not None:
            return exact_result

        # 4. L2 Semantic Cache Lookup
        semantic_result, query_vector = await self._try_semantic_cache(
            identity=identity,
            norm_req=norm_req,
            raw_requested_model=raw_requested_model,
            request_id=request_id,
            exact_request_hash=exact_request_hash,
            scope_hash=scope_hash,
            system_prompt=system_prompt,
            last_user_text=last_user_text,
            gateway_start_ns=gateway_start_ns,
            exact_cache_lookup_ms=exact_cache_lookup_ms,
            db=db,
        )
        if semantic_result is not None:
            return semantic_result

        # 5. Cache Miss -> Streaming vs Non-Streaming Pathway
        if norm_req.stream:
            return await self._execute_stream_miss(
                identity=identity,
                norm_req=norm_req,
                raw_requested_model=raw_requested_model,
                request_id=request_id,
                exact_request_hash=exact_request_hash,
                scope_hash=scope_hash,
                system_prompt=system_prompt,
                last_user_text=last_user_text,
                gateway_start_ns=gateway_start_ns,
                exact_cache_lookup_ms=exact_cache_lookup_ms,
                db=db,
            )

        return await self._execute_nonstream_miss(
            identity=identity,
            norm_req=norm_req,
            raw_requested_model=raw_requested_model,
            request_id=request_id,
            exact_request_hash=exact_request_hash,
            scope_hash=scope_hash,
            system_prompt=system_prompt,
            last_user_text=last_user_text,
            query_vector=query_vector,
            gateway_start_ns=gateway_start_ns,
            exact_cache_lookup_ms=exact_cache_lookup_ms,
            db=db,
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
