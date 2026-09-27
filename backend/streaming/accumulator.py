import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.auth.identity import AuthenticatedIdentity
from backend.caching.factory import get_cache_backend
from backend.caching.models import CachedResponse
from backend.normalization.models import NormalizedInferenceRequest
from backend.metrics.collector import get_metrics_collector
from backend.semantic.factory import get_semantic_cache_service
from backend.telemetry.service import TelemetryService

logger = logging.getLogger(__name__)


class StreamAccumulator:
    """
    T-Junction Stream Tap:
    Passes SSE chunks downstream to the client with minimum TTFT latency
    while accumulating the complete LLM response payload on-the-fly for
    dual L1 + L2 cache backfill and telemetry logging upon stream completion.
    """

    def __init__(
        self,
        upstream_stream: AsyncIterator[str],
        request_id: str,
        identity: AuthenticatedIdentity,
        norm_req: NormalizedInferenceRequest,
        exact_request_hash: str,
        scope_hash: str,
        last_user_text: str,
        system_prompt: Optional[str],
        gateway_start_ns: int,
        exact_cache_lookup_ms: float,
        db: AsyncSession,
        provider_used: Optional[str] = None,
        fallback_hops: int = 0,
    ) -> None:
        self.upstream_stream = upstream_stream
        self.request_id = request_id
        self.identity = identity
        self.norm_req = norm_req
        self.exact_request_hash = exact_request_hash
        self.scope_hash = scope_hash
        self.last_user_text = last_user_text
        self.system_prompt = system_prompt
        self.gateway_start_ns = gateway_start_ns
        self.exact_cache_lookup_ms = exact_cache_lookup_ms
        self.db = db
        self.provider_used = provider_used or norm_req.provider
        self.fallback_hops = fallback_hops

        # Accumulation State
        self.accumulated_chunks: List[str] = []
        self.accumulated_role: str = "assistant"
        self.accumulated_finish_reason: str = "stop"
        self.accumulated_model: str = norm_req.model
        self.accumulated_system_fingerprint: Optional[str] = None
        self.accumulated_usage: Optional[Dict[str, int]] = None
        self.created_ts: Optional[int] = None
        self.first_token_time_ns: Optional[int] = None

    async def __aiter__(self) -> AsyncIterator[str]:
        upstream_start_ns = time.perf_counter_ns()
        try:
            async for chunk in self.upstream_stream:
                if not chunk:
                    continue

                if self.first_token_time_ns is None:
                    self.first_token_time_ns = time.perf_counter_ns()

                # 1. Yield chunk immediately to client (zero-latency pass-through)
                yield chunk

                # 2. Parse and accumulate chunk data
                self._parse_and_accumulate(chunk)

        except Exception as exc:
            logger.error("Error during streaming response pass-through: %s", exc)
            raise
        finally:
            upstream_end_ns = time.perf_counter_ns()
            upstream_latency_ms = (upstream_end_ns - upstream_start_ns) / 1_000_000
            await self._finalize_stream(upstream_latency_ms)

    def _parse_and_accumulate(self, sse_line: str) -> None:
        """Parses SSE chunk line and accumulates token deltas."""
        lines = sse_line.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line.startswith("data:"):
                continue

            data_str = line[len("data:"):].strip()
            if not data_str or data_str == "[DONE]":
                continue

            try:
                data = json.loads(data_str)
                if "model" in data:
                    self.accumulated_model = data["model"]
                if "system_fingerprint" in data:
                    self.accumulated_system_fingerprint = data["system_fingerprint"]
                if "created" in data and self.created_ts is None:
                    self.created_ts = data["created"]
                if "usage" in data and data["usage"]:
                    self.accumulated_usage = data["usage"]

                choices = data.get("choices", [])
                if choices:
                    choice = choices[0]
                    delta = choice.get("delta", {})
                    if "role" in delta and delta["role"]:
                        self.accumulated_role = delta["role"]
                    if "content" in delta and delta["content"]:
                        self.accumulated_chunks.append(delta["content"])
                    if "finish_reason" in choice and choice["finish_reason"]:
                        self.accumulated_finish_reason = choice["finish_reason"]

            except Exception:
                # Malformed SSE data chunk; ignore parsing error for this line
                pass

    async def _finalize_stream(self, upstream_latency_ms: float) -> None:
        """Constructs canonical response, performs dual cache backfill, and logs telemetry."""
        full_content = "".join(self.accumulated_chunks)
        gateway_latency_ms = (time.perf_counter_ns() - self.gateway_start_ns) / 1_000_000

        # Calculate token counts
        if self.accumulated_usage:
            input_tokens = self.accumulated_usage.get("prompt_tokens", 0)
            output_tokens = self.accumulated_usage.get("completion_tokens", 0)
        else:
            input_tokens = sum(len(str(m.content or "")) // 4 + 4 for m in self.norm_req.messages)
            output_tokens = max(1, len(full_content) // 4)

        raw_response: Dict[str, Any] = {
            "id": self.request_id,
            "object": "chat.completion",
            "created": self.created_ts or int(time.time()),
            "model": self.accumulated_model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": self.accumulated_role,
                        "content": full_content,
                    },
                    "finish_reason": self.accumulated_finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }
        if self.accumulated_system_fingerprint:
            raw_response["system_fingerprint"] = self.accumulated_system_fingerprint

        # 1. Determine TTL via Volatility Engine
        semantic_service = get_semantic_cache_service()
        ttl_seconds = settings.DEFAULT_CACHE_TTL_SECONDS
        if self.last_user_text:
            try:
                volatility_info = await semantic_service.volatility_engine.classify(self.last_user_text)
                ttl_seconds = volatility_info.ttl_seconds
            except Exception:
                ttl_seconds = settings.DEFAULT_CACHE_TTL_SECONDS

        # 2. Backfill L1 Exact Cache
        try:
            cache_backend = get_cache_backend()
            cached_entry = CachedResponse(
                exact_request_hash=self.exact_request_hash,
                response_payload=raw_response,
                provider=self.provider_used,
                model=self.accumulated_model,
                ttl_seconds=ttl_seconds,
                namespace=self.norm_req.namespace,
                tags=self.norm_req.tags,
            )
            await cache_backend.set(
                self.identity.project_id,
                self.exact_request_hash,
                cached_entry,
                ttl_seconds,
            )
        except Exception as exc:
            logger.error("Failed to backfill L1 cache in stream accumulator: %s", exc)

        # 3. Backfill L2 Semantic Cache
        if self.last_user_text:
            try:
                query_vector = await semantic_service.embedding_engine.embed(self.last_user_text)
                semantic_payload = dict(raw_response)
                semantic_payload["__cachemind_input_text__"] = self.last_user_text
                semantic_payload["__cachemind_system_prompt__"] = self.system_prompt

                await semantic_service.vector_index.insert(
                    scope_hash=self.scope_hash,
                    exact_request_hash=self.exact_request_hash,
                    vector=query_vector,
                    response_payload=semantic_payload,
                    created_at=time.time(),
                )
            except Exception as exc:
                logger.error("Failed to backfill L2 vector index in stream accumulator: %s", exc)

        # 4. Record Telemetry Log & Prometheus Metrics
        try:
            await TelemetryService.record_request_log(
                db=self.db,
                request_id=self.request_id,
                tenant_id=self.identity.tenant_id,
                project_id=self.identity.project_id,
                provider=self.provider_used,
                requested_model=self.norm_req.model,
                actual_model=self.accumulated_model,
                cache_status="MISS",
                exact_request_hash=self.exact_request_hash,
                gateway_latency_ms=gateway_latency_ms,
                upstream_latency_ms=upstream_latency_ms,
                exact_cache_lookup_ms=self.exact_cache_lookup_ms,
                upstream_called=True,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                similarity_score=None,
                guardrail_status=None,
                guardrail_failed_check=None,
            )
            get_metrics_collector().record_request(
                tenant_id=self.identity.tenant_id,
                provider=self.provider_used,
                model=self.norm_req.model,
                cache_status="MISS",
                gateway_latency_ms=gateway_latency_ms,
                upstream_latency_ms=upstream_latency_ms,
                cache_lookup_ms=self.exact_cache_lookup_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception as exc:
            logger.error("Failed to record telemetry in stream accumulator: %s", exc)
