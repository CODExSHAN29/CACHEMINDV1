import logging
import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.auth.dependencies import get_authenticated_identity
from backend.auth.identity import AuthenticatedIdentity
from backend.db.session import get_db
from backend.inference.pipeline import get_inference_pipeline
from backend.metrics.collector import get_metrics_collector
from backend.normalization.openai_adapter import OpenAIAdapter
from backend.providers.base import ProviderError
from backend.ratelimit.limiter import get_rate_limiter
from backend.routing.engine import InvalidFallbackConfigurationError
from backend.routing.model_catalog import UnknownModelError, resolve_model
from backend.security.pii import PIISanitizer, PIIBlockedException, resolve_pii_mode

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

    # 3. Transport-Neutral Inference Execution
    pipeline = get_inference_pipeline()
    try:
        result = await pipeline.execute(
            norm_req=norm_req,
            identity=identity,
            db=db,
            raw_requested_model=raw_requested_model,
            request_id=request_id,
            gateway_start_ns=gateway_start_ns,
        )
    except ProviderError as pe:
        status_code = pe.status_code if pe.status_code and pe.status_code >= 400 else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status_code,
            detail=pe.safe_message,
        )
    except InvalidFallbackConfigurationError as fe:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(fe),
        )
    except Exception as exc:
        logger.exception("Inference execution failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="An unexpected upstream error occurred.",
        )

    response_headers = {**result.headers, **rl_headers}

    # 4. Serialize HTTP Response
    if result.is_stream and result.stream_generator is not None:
        return StreamingResponse(
            result.stream_generator,
            media_type="text/event-stream",
            headers=response_headers,
        )

    return JSONResponse(
        content=result.response_body,
        headers=response_headers,
    )
