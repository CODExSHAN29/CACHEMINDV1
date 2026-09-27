import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import RequestLog
from backend.db.repositories import RequestLogRepository

logger = logging.getLogger(__name__)


class TelemetryService:
    @staticmethod
    async def record_request_log(
        db: AsyncSession,
        request_id: str,
        tenant_id: str,
        project_id: str,
        provider: str,
        requested_model: str,
        actual_model: str,
        cache_status: str,
        exact_request_hash: str,
        gateway_latency_ms: float,
        upstream_latency_ms: Optional[float],
        exact_cache_lookup_ms: float,
        upstream_called: bool,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        similarity_score: Optional[float] = None,
        guardrail_status: Optional[bool] = None,
        guardrail_failed_check: Optional[str] = None,
    ) -> Optional[RequestLog]:
        """
        Durable telemetry recording to SQL metadata repository.
        """
        try:
            repo = RequestLogRepository(db)
            return await repo.create_log(
                request_id=request_id,
                tenant_id=tenant_id,
                project_id=project_id,
                provider=provider,
                requested_model=requested_model,
                actual_model=actual_model,
                cache_status=cache_status,
                exact_request_hash=exact_request_hash,
                gateway_latency_ms=gateway_latency_ms,
                upstream_latency_ms=upstream_latency_ms,
                exact_cache_lookup_ms=exact_cache_lookup_ms,
                upstream_called=upstream_called,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                similarity_score=similarity_score,
                guardrail_status=guardrail_status,
                guardrail_failed_check=guardrail_failed_check,
            )
        except Exception as err:
            logger.error("Failed to record request telemetry log: %s", err)
            return None
