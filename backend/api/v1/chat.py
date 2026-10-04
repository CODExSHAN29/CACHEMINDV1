import logging
import time
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.auth.dependencies import get_authenticated_identity
from backend.auth.identity import AuthenticatedIdentity
from backend.caching.coalescer import get_request_coalescer
from backend.caching.factory import get_cache_backend
from backend.caching.fingerprint import compute_exact_request_hash, compute_scope_hash, extract_system_prompt
from backend.caching.models import CachedResponse
from backend.db.session import get_db
from backend.normalization.openai_adapter import OpenAIAdapter
from backend.metrics.collector import get_metrics_collector
from backend.providers.base import ProviderError
from backend.ratelimit.limiter import get_rate_limiter
from backend.routing.engine import (
    InvalidFallbackConfigurationError,
    get_routing_engine,
)
from backend.routing.model_catalog import UnknownModelError, resolve_model
from backend.security.pii import PIISanitizer, PIIBlockedException, resolve_pii_mode
from backend.streaming.accumulator import StreamAccumulator
from backend.streaming.sse import create_cached_stream_generator
from backend.telemetry.service import TelemetryService
from backend.semantic.factory import get_semantic_cache_service
from backend.semantic.policy import evaluate_semantic_eligibility

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Chat Completions"])


@router.post("/chat/completions")
async def create_chat_completion(
    request: Request,
    db: AsyncSession = Depends(get_db),
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> Response:
    gateway_start_ns = time.perf_counter_ns()
    request_id = str(uuid.uuid4())

    try:
        payload: Dict[str, Any] = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {str(exc)}",
        )

    # 1. Parse & Normalize Request
    try:
        norm_req = OpenAIAdapter.parse_request(payload)
        raw_requested_model = norm_req.model

        # Early Authoritative Model Resolution & Fail-Fast Validation
        try:
            resolved_target = resolve_model(norm_req.model)
        except UnknownModelError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

        norm_req.provider = resolved_target.provider
        norm_req.model = resolved_target.canonical_model

        # Check headers for namespace and tags if not present in body
        hdr_ns = request.headers.get("X-CacheMind-Namespace")
        if hdr_ns and not norm_req.namespace:
            norm_req.namespace = hdr_ns.strip()

        hdr_tags = request.headers.get("X-CacheMind-Tags")
        if hdr_tags and not norm_req.tags:
            norm_req.tags = [t.strip() for t in hdr_tags.split(",") if t.strip()]

        hdr_fallback = request.headers.get("X-CacheMind-Allow-Fallback") or request.headers.get("X-CacheMind-Fallback")
        if hdr_fallback is not None:
            norm_req.allow_provider_fallback = hdr_fallback.strip().lower() in ("true", "1", "yes")

        # PII Policy Resolution & Sanitization
        hdr_pii = request.headers.get("X-CacheMind-PII-Mode")
        try:
            effective_pii_mode = resolve_pii_mode(
                server_mode=settings.PII_MASKING_MODE,
                requested_mode=hdr_pii,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

        PIISanitizer.sanitize_messages(norm_req.messages, mode=effective_pii_mode)

    except PIIBlockedException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "message": str(exc),
                    "type": "pii_blocked",
                    "code": "pii_detected",
                    "entities": [
                        {"type": e.entity_type, "start": e.start, "end": e.end}
                        for e in exc.entities
                    ],
                }
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request parsing error: {str(exc)}",
        )

    # 2. Multi-Tenant Rate Limiter Check (RPM & TPM)
    rate_limiter = get_rate_limiter()
    # Estimate input tokens for TPM check
    messages_dicts = [m.model_dump() if hasattr(m, "model_dump") else m.dict() for m in norm_req.messages]
    estimated_tokens = sum(len(str(m.get("content") or "")) // 4 + 4 for m in messages_dicts) or 100

    rate_limit_result = await rate_limiter.check_and_consume(
        tenant_id=identity.tenant_id,
        project_id=identity.project_id,
        estimated_tokens=estimated_tokens,
    )
    rl_headers = rate_limit_result.to_headers()

    if not rate_limit_result.allowed:
        get_metrics_collector().record_rate_limit_rejection(identity.tenant_id, "rpm")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "message": "Rate limit exceeded. Please retry after some time.",
                    "type": "requests",
                    "param": None,
                    "code": "rate_limit_exceeded",
                }
            },
            headers=rl_headers,
        )

    # Inference permission check
    if not identity.can_infer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key role does not permit inference operations.",
        )

    # 3. Derive Exact Hash (Strictly bound to authenticated tenant, project, resolved provider & model)
    exact_request_hash = compute_exact_request_hash(
        tenant_id=identity.tenant_id,
        project_id=identity.project_id,
        provider=norm_req.provider,
        model=norm_req.model,
        request=norm_req,
    )

    cache_backend = get_cache_backend()
    coalescer = get_request_coalescer()
    coalesce_key = f"{identity.tenant_id}:{identity.project_id}:{exact_request_hash}"

    # 4. L1 EXACT CACHE LOOKUP
    cache_start_ns = time.perf_counter_ns()
    cached = await cache_backend.get(identity.project_id, exact_request_hash)
    exact_cache_lookup_ms = (time.perf_counter_ns() - cache_start_ns) / 1_000_000

    if cached is not None:
        # EXACT HIT
        was_coalesced = coalescer.is_recent(coalesce_key)
        cache_status = "EXACT_HIT"
        upstream_called = False
        upstream_latency_ms = None

        await cache_backend.increment_hit(identity.project_id, exact_request_hash)

        response_body = OpenAIAdapter.format_cached_response(
            cached.response_payload, request_id, raw_requested_model
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
            provider=cached.provider or norm_req.provider,
            requested_model=raw_requested_model,
            actual_model=cached.model or norm_req.model,
            cache_status=cache_status,
            exact_request_hash=exact_request_hash,
            gateway_latency_ms=gateway_latency_ms,
            upstream_latency_ms=upstream_latency_ms,
            exact_cache_lookup_ms=exact_cache_lookup_ms,
            upstream_called=upstream_called,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            similarity_score=1.0,
            guardrail_status=True,
            guardrail_failed_check=None,
        )

        get_metrics_collector().record_request(
            tenant_id=identity.tenant_id,
            provider=cached.provider or norm_req.provider,
            model=cached.model or norm_req.model,
            cache_status="EXACT_HIT",
            gateway_latency_ms=gateway_latency_ms,
            upstream_latency_ms=None,
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
            "X-CacheMind-Provider": cached.provider or norm_req.provider,
            "X-CacheMind-Model": cached.model or norm_req.model,
            "X-CacheMind-Fallback-Hops": "0",
            "X-CacheMind-Coalesced": "true" if was_coalesced else "false",
            **rl_headers,
        }

        if norm_req.stream:
            stream_gen = create_cached_stream_generator(
                cached_payload=cached.response_payload,
                request_id=request_id,
                model=raw_requested_model,
            )
            return StreamingResponse(stream_gen, media_type="text/event-stream", headers=headers)

        return JSONResponse(content=response_body, headers=headers)

    # 5. L2 SEMANTIC CACHE LOOKUP (Opt-in and fail-closed)
    semantic_service = get_semantic_cache_service()
    system_prompt = extract_system_prompt(norm_req)
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

    last_user_text = OpenAIAdapter.extract_last_user_message(messages_dicts) or ""
    coalescer = get_request_coalescer()
    coalesce_key = f"{identity.tenant_id}:{identity.project_id}:{exact_request_hash}"

    query_vector: Optional[list] = None
    if settings.SEMANTIC_CACHE_MODE == "safe" and last_user_text and not coalescer.is_in_flight(coalesce_key):
        semantic_eligibility = evaluate_semantic_eligibility(norm_req)
        if semantic_eligibility.eligible:
            try:
                query_vector = await semantic_service.embedding_engine.embed(last_user_text)
                candidates = await semantic_service.backend.search(
                    query_vector=query_vector,
                    scope_hash=scope_hash,
                    top_k=5,
                    similarity_threshold=settings.VECTOR_SIMILARITY_THRESHOLD,
                )

                for cand in candidates:
                    cand_payload = cand.response_payload
                    cand_text = cand_payload.get("__cachemind_input_text__", "")
                    cand_sys_prompt = cand_payload.get("__cachemind_system_prompt__", None)

                    decision = await semantic_service.arbiter.evaluate(
                        incoming_text=last_user_text,
                        candidate_text=cand_text or last_user_text,
                        incoming_system_prompt=system_prompt,
                        candidate_system_prompt=cand_sys_prompt or system_prompt,
                    )

                    if decision.passed:
                        # L2 SEMANTIC HIT!
                        cache_status = "L2_HIT"
                        upstream_called = False
                        upstream_latency_ms = None

                        cleaned_payload = {k: v for k, v in cand_payload.items() if not k.startswith("__cachemind_")}
                        response_body = OpenAIAdapter.format_cached_response(
                            cleaned_payload, request_id, raw_requested_model
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
                            cache_status=cache_status,
                            exact_request_hash=exact_request_hash,
                            gateway_latency_ms=gateway_latency_ms,
                            upstream_latency_ms=upstream_latency_ms,
                            exact_cache_lookup_ms=exact_cache_lookup_ms,
                            upstream_called=upstream_called,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            similarity_score=cand.similarity,
                            guardrail_status=True,
                            guardrail_failed_check=None,
                        )

                        get_metrics_collector().record_request(
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
                            **rl_headers,
                        }

                        if norm_req.stream:
                            stream_gen = create_cached_stream_generator(
                                cached_payload=cleaned_payload,
                                request_id=request_id,
                                model=raw_requested_model,
                            )
                            return StreamingResponse(stream_gen, media_type="text/event-stream", headers=headers)

                        return JSONResponse(content=response_body, headers=headers)
            except Exception as exc:
                logger.warning("L2 semantic cache lookup failed for request %s: %s", request_id, exc)
                get_metrics_collector().record_error(
                    error_type="semantic_cache_lookup_error",
                    tenant_id=identity.tenant_id,
                )

    # 6. CACHE MISS -> Resilient Routing Engine with Circuit Breakers & Fallbacks
    cache_status = "MISS"
    routing_engine = get_routing_engine()

    if norm_req.stream:
        try:
            streaming_result = await routing_engine.execute_stream(norm_req)
            # Compute actual fallback hashes for streaming BEFORE constructing accumulator
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
                last_user_text=last_user_text,
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
                **rl_headers,
            }
            return StreamingResponse(accumulator, media_type="text/event-stream", headers=headers)
        except HTTPException:
            raise
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
            status_code = pe.status_code if pe.status_code and pe.status_code >= 400 else status.HTTP_502_BAD_GATEWAY
            raise HTTPException(
                status_code=status_code,
                detail=pe.safe_message,
            )
        except InvalidFallbackConfigurationError as fe:
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(fe),
            )
        except Exception as exc:
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
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="An unexpected upstream error occurred.",
            )

    # Non-streaming Cache Miss pathway with Single-Flight Coalescing
    upstream_called = True
    upstream_start_ns = time.perf_counter_ns()
    coalescer = get_request_coalescer()
    coalesce_key = f"{identity.tenant_id}:{identity.project_id}:{exact_request_hash}"
    was_coalesced = False
    try:
        routing_result, was_coalesced = await coalescer.do(
            coalesce_key,
            lambda: routing_engine.execute(norm_req),
        )
        provider_resp = routing_result.response
        upstream_latency_ms = (time.perf_counter_ns() - upstream_start_ns) / 1_000_000
    except HTTPException:
        raise
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
        status_code = pe.status_code if pe.status_code and pe.status_code >= 400 else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status_code,
            detail=pe.safe_message,
        )
    except InvalidFallbackConfigurationError as fe:
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(fe),
        )
    except Exception as exc:
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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="An unexpected upstream error occurred.",
        )

    # 7. DUAL BACKFILL: Populate L1 Exact Cache + L2 Semantic Cache on Success
    ttl_seconds = settings.DEFAULT_CACHE_TTL_SECONDS
    if last_user_text:
        try:
            volatility_info = await semantic_service.volatility_engine.classify(last_user_text)
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

    # 7a. L1 Exact Cache Set
    cached_entry = CachedResponse(
        exact_request_hash=backfill_exact_hash,
        response_payload=provider_resp.raw_response,
        provider=routing_result.provider_used,
        model=routing_result.model_used,
        ttl_seconds=ttl_seconds,
        namespace=norm_req.namespace,
        tags=norm_req.tags,
    )
    await cache_backend.set(
        identity.project_id,
        backfill_exact_hash,
        cached_entry,
        ttl_seconds,
    )

    # 7b. L2 Semantic Vector Backend Insert (Opt-in and fail-closed)
    if settings.SEMANTIC_CACHE_MODE == "safe" and last_user_text:
        eligibility = evaluate_semantic_eligibility(norm_req)
        if eligibility.eligible:
            try:
                if query_vector is None:
                    query_vector = await semantic_service.embedding_engine.embed(last_user_text)

                semantic_payload = dict(provider_resp.raw_response)
                semantic_payload["__cachemind_input_text__"] = last_user_text
                semantic_payload["__cachemind_system_prompt__"] = system_prompt

                await semantic_service.backend.insert(
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
                get_metrics_collector().record_error(
                    error_type="semantic_cache_insert_error",
                    tenant_id=identity.tenant_id,
                )

    gateway_latency_ms = (time.perf_counter_ns() - gateway_start_ns) / 1_000_000

    # Determine effective hash for telemetry and response headers
    effective_exact_hash = backfill_exact_hash if routing_result.provider_used != norm_req.provider or routing_result.model_used != norm_req.model else exact_request_hash

    # 8. Telemetry Logging
    await TelemetryService.record_request_log(
        db=db,
        request_id=request_id,
        tenant_id=identity.tenant_id,
        project_id=identity.project_id,
        provider=routing_result.provider_used,
        requested_model=raw_requested_model,
        actual_model=routing_result.model_used,
        cache_status=cache_status,
        exact_request_hash=effective_exact_hash,
        gateway_latency_ms=gateway_latency_ms,
        upstream_latency_ms=upstream_latency_ms,
        exact_cache_lookup_ms=exact_cache_lookup_ms,
        upstream_called=upstream_called,
        input_tokens=provider_resp.input_tokens,
        output_tokens=provider_resp.output_tokens,
        similarity_score=None,
        guardrail_status=None,
        guardrail_failed_check=None,
    )

    get_metrics_collector().record_request(
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
        **rl_headers,
    }
    return JSONResponse(content=provider_resp.raw_response, headers=headers)
