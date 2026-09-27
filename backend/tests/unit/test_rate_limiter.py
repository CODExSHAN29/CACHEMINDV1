import asyncio
import pytest
from backend.ratelimit.limiter import InMemoryTokenBucket, RateLimiter
from backend.ratelimit.models import RateLimitResult


@pytest.mark.asyncio
async def test_token_bucket_rpm_consumption():
    bucket = InMemoryTokenBucket(rpm_limit=3, tpm_limit=1000)

    # 1. First 3 requests succeed
    for _ in range(3):
        allowed, rem_rpm, rem_tpm, retry_after = await bucket.consume(1, 10)
        assert allowed is True
        assert retry_after == 0

    # 2. 4th request exceeds RPM
    allowed, rem_rpm, rem_tpm, retry_after = await bucket.consume(1, 10)
    assert allowed is False
    assert retry_after >= 1


@pytest.mark.asyncio
async def test_token_bucket_tpm_consumption():
    bucket = InMemoryTokenBucket(rpm_limit=100, tpm_limit=150)

    # Consume 100 tokens
    allowed, rem_rpm, rem_tpm, retry_after = await bucket.consume(1, 100)
    assert allowed is True
    assert rem_tpm == 50

    # Attempting to consume 100 tokens fails
    allowed, rem_rpm, rem_tpm, retry_after = await bucket.consume(1, 100)
    assert allowed is False
    assert retry_after >= 1


@pytest.mark.asyncio
async def test_rate_limiter_tenant_isolation():
    limiter = RateLimiter()

    # Exhaust Tenant A's quota
    for _ in range(2):
        res = await limiter.check_and_consume("tenant_a", "proj_1", estimated_tokens=10, rpm_limit=2, tpm_limit=500)
        assert res.allowed is True

    res_a_rejected = await limiter.check_and_consume("tenant_a", "proj_1", estimated_tokens=10, rpm_limit=2, tpm_limit=500)
    assert res_a_rejected.allowed is False

    # Tenant B remains unaffected
    res_b = await limiter.check_and_consume("tenant_b", "proj_1", estimated_tokens=10, rpm_limit=2, tpm_limit=500)
    assert res_b.allowed is True


def test_rate_limit_result_headers():
    res = RateLimitResult(
        allowed=False,
        remaining_requests=0,
        limit_requests=10,
        remaining_tokens=50,
        limit_tokens=1000,
        reset_seconds=60,
        retry_after=5,
    )
    headers = res.to_headers()
    assert headers["X-RateLimit-Limit-Requests"] == "10"
    assert headers["X-RateLimit-Remaining-Requests"] == "0"
    assert headers["Retry-After"] == "5"
