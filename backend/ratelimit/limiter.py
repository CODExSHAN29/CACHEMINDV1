import asyncio
import logging
import time
from typing import Dict, Optional, Tuple
from fastapi import HTTPException, status

from backend.app.config import settings
from backend.ratelimit.models import RateLimitResult

logger = logging.getLogger(__name__)


class InMemoryTokenBucket:
    """
    Thread-safe, sliding token bucket tracking both RPM and TPM in local memory.
    """

    def __init__(self, rpm_limit: int, tpm_limit: int) -> None:
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit

        self.request_tokens = float(rpm_limit)
        self.token_tokens = float(tpm_limit)

        self.last_refill = time.time()
        self._lock: Optional[asyncio.Lock] = None

    @property
    def lock(self) -> asyncio.Lock:
        """Lazy lock creation ensures binding to the current event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _refill(self, now: float) -> None:
        elapsed = now - self.last_refill
        if elapsed <= 0:
            return

        # Refill rate = limit / 60.0 per second
        self.request_tokens = min(
            float(self.rpm_limit),
            self.request_tokens + elapsed * (self.rpm_limit / 60.0),
        )
        self.token_tokens = min(
            float(self.tpm_limit),
            self.token_tokens + elapsed * (self.tpm_limit / 60.0),
        )
        self.last_refill = now

    async def consume(
        self, requested_tokens: int = 1, estimated_llm_tokens: int = 100
    ) -> Tuple[bool, int, int, int]:
        """
        Attempts to consume 1 request token and estimated LLM tokens.
        Returns: (allowed, remaining_rpm, remaining_tpm, retry_after)
        """
        async with self.lock:
            now = time.time()
            self._refill(now)

            has_rpm = self.request_tokens >= requested_tokens
            has_tpm = self.token_tokens >= estimated_llm_tokens

            if has_rpm and has_tpm:
                self.request_tokens -= requested_tokens
                self.token_tokens -= estimated_llm_tokens
                return (
                    True,
                    int(self.request_tokens),
                    int(self.token_tokens),
                    0,
                )

            # Calculate retry after in seconds
            retry_after_rpm = 0.0
            if not has_rpm:
                needed = requested_tokens - self.request_tokens
                retry_after_rpm = needed / (self.rpm_limit / 60.0)

            retry_after_tpm = 0.0
            if not has_tpm:
                needed = estimated_llm_tokens - self.token_tokens
                retry_after_tpm = needed / (self.tpm_limit / 60.0)

            retry_after = max(1, int(max(retry_after_rpm, retry_after_tpm)))
            return (
                False,
                int(self.request_tokens),
                int(self.token_tokens),
                retry_after,
            )


class RateLimiter:
    """
    Multi-tenant Rate Limiting subsystem.
    Enforces RPM (Requests Per Minute) and TPM (Tokens Per Minute) quotas per tenant/project
    with fail-open resilience and standard RFC rate-limit response headers.
    """

    def __init__(self) -> None:
        self._buckets: Dict[str, InMemoryTokenBucket] = {}
        self._lock: Optional[asyncio.Lock] = None

    @property
    def lock(self) -> asyncio.Lock:
        """Lazy lock creation ensures binding to the current event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _get_bucket_key(self, tenant_id: str, project_id: str) -> str:
        return f"{tenant_id}:{project_id}"

    async def get_or_create_bucket(
        self,
        tenant_id: str,
        project_id: str,
        rpm_limit: Optional[int] = None,
        tpm_limit: Optional[int] = None,
    ) -> InMemoryTokenBucket:
        key = self._get_bucket_key(tenant_id, project_id)
        async with self.lock:
            if key not in self._buckets:
                rpm = rpm_limit or settings.DEFAULT_RPM_LIMIT
                tpm = tpm_limit or settings.DEFAULT_TPM_LIMIT
                self._buckets[key] = InMemoryTokenBucket(rpm_limit=rpm, tpm_limit=tpm)
            else:
                bucket = self._buckets[key]
                if rpm_limit is not None and bucket.rpm_limit != rpm_limit:
                    bucket.rpm_limit = rpm_limit
                    bucket.request_tokens = min(bucket.request_tokens, float(rpm_limit))
                if tpm_limit is not None and bucket.tpm_limit != tpm_limit:
                    bucket.tpm_limit = tpm_limit
                    bucket.token_tokens = min(bucket.token_tokens, float(tpm_limit))
            return self._buckets[key]

    async def check_and_consume(
        self,
        tenant_id: str,
        project_id: str,
        estimated_tokens: int = 100,
        rpm_limit: Optional[int] = None,
        tpm_limit: Optional[int] = None,
    ) -> RateLimitResult:
        """
        Evaluates and consumes tenant quota.
        Guarantees fail-open behavior on internal errors.
        """
        if not settings.RATE_LIMIT_ENABLED:
            return RateLimitResult(
                allowed=True,
                remaining_requests=settings.DEFAULT_RPM_LIMIT,
                limit_requests=settings.DEFAULT_RPM_LIMIT,
                remaining_tokens=settings.DEFAULT_TPM_LIMIT,
                limit_tokens=settings.DEFAULT_TPM_LIMIT,
                reset_seconds=60,
                retry_after=0,
            )

        try:
            bucket = await self.get_or_create_bucket(
                tenant_id, project_id, rpm_limit, tpm_limit
            )
            allowed, rem_rpm, rem_tpm, retry_after = await bucket.consume(
                requested_tokens=1, estimated_llm_tokens=estimated_tokens
            )

            return RateLimitResult(
                allowed=allowed,
                remaining_requests=rem_rpm,
                limit_requests=bucket.rpm_limit,
                remaining_tokens=rem_tpm,
                limit_tokens=bucket.tpm_limit,
                reset_seconds=60,
                retry_after=retry_after,
            )
        except Exception as exc:
            # Fail-open strategy: allow traffic if rate limiter fails
            logger.error("Rate limiter exception (failing open): %s", exc)
            return RateLimitResult(
                allowed=True,
                remaining_requests=100,
                limit_requests=100,
                remaining_tokens=100_000,
                limit_tokens=100_000,
                reset_seconds=60,
                retry_after=0,
            )

    def reset_sync(self, tenant_id: Optional[str] = None) -> None:
        """Synchronously resets all or specific tenant buckets."""
        if tenant_id is None:
            self._buckets.clear()
        else:
            to_delete = [k for k in self._buckets if k.startswith(f"{tenant_id}:")]
            for k in to_delete:
                self._buckets.pop(k, None)

    async def reset(self, tenant_id: Optional[str] = None) -> None:
        """Resets all or specific tenant buckets."""
        async with self.lock:
            self.reset_sync(tenant_id)


_rate_limiter_instance: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = RateLimiter()
    return _rate_limiter_instance


def set_rate_limiter(limiter: RateLimiter) -> None:
    global _rate_limiter_instance
    _rate_limiter_instance = limiter
