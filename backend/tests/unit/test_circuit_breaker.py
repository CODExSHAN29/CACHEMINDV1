import asyncio
import pytest
from backend.resilience.circuit_breaker import CircuitBreaker, CircuitState


@pytest.mark.asyncio
async def test_breaker_starts_closed():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=30.0)
    assert cb._state == CircuitState.CLOSED
    assert await cb.can_execute() is True


@pytest.mark.asyncio
async def test_breaker_transitions_closed_to_open_on_threshold():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=30.0)
    await cb.record_failure()
    assert cb._state == CircuitState.CLOSED
    await cb.record_failure()
    assert cb._state == CircuitState.CLOSED
    await cb.record_failure()
    assert cb._state == CircuitState.OPEN
    assert await cb.can_execute() is False


@pytest.mark.asyncio
async def test_open_to_half_open_after_recovery_cooldown():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.05)
    await cb.record_failure()
    await cb.record_failure()
    assert cb._state == CircuitState.OPEN
    assert await cb.can_execute() is False

    await asyncio.sleep(0.08)
    assert await cb.can_execute() is True
    assert cb._state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_success_resets_to_closed():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.05)
    await cb.record_failure()
    await cb.record_failure()
    await asyncio.sleep(0.08)
    assert await cb.can_execute() is True
    await cb.record_success()
    assert cb._state == CircuitState.CLOSED
    assert await cb.can_execute() is True


@pytest.mark.asyncio
async def test_half_open_failure_reopens():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.05)
    await cb.record_failure()
    await cb.record_failure()
    await asyncio.sleep(0.08)
    assert await cb.can_execute() is True  # Enters HALF_OPEN
    await cb.record_failure()
    assert cb._state == CircuitState.OPEN
    assert await cb.can_execute() is False
