import asyncio
import pytest

from backend.caching.coalescer import RequestCoalescer, get_request_coalescer


@pytest.mark.asyncio
async def test_request_coalescer_deduplicates_concurrent_calls():
    coalescer = RequestCoalescer()
    call_count = 0

    async def slow_work():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return "work_result"

    # Launch 5 concurrent calls with the same key
    tasks = [
        asyncio.create_task(coalescer.do("test_key", slow_work))
        for _ in range(5)
    ]

    results = await asyncio.gather(*tasks)

    # All 5 callers get the exact same result
    assert len(results) == 5
    for val, is_follower in results:
        assert val == "work_result"

    # Only 1 actual execution happened
    assert call_count == 1

    # Exactly 1 was leader (is_follower=False) and 4 were followers (is_follower=True)
    leaders = [r for r in results if not r[1]]
    followers = [r for r in results if r[1]]
    assert len(leaders) == 1
    assert len(followers) == 4

    # Map is cleaned up afterwards
    assert coalescer.in_flight_count() == 0
    assert coalescer.is_in_flight("test_key") is False


@pytest.mark.asyncio
async def test_request_coalescer_distinct_keys_execute_independently():
    coalescer = RequestCoalescer()
    call_count = 0

    async def do_work(key: str):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.02)
        return f"result_{key}"

    tasks = [
        asyncio.create_task(coalescer.do(f"key_{i}", lambda k=f"key_{i}": do_work(k)))
        for i in range(3)
    ]

    results = await asyncio.gather(*tasks)
    assert call_count == 3
    for i, (val, is_follower) in enumerate(results):
        assert val == f"result_key_{i}"
        assert is_follower is False


@pytest.mark.asyncio
async def test_request_coalescer_propagates_exceptions_to_all_callers():
    coalescer = RequestCoalescer()

    async def failing_work():
        await asyncio.sleep(0.03)
        raise ValueError("Upstream exploded")

    tasks = [
        asyncio.create_task(coalescer.do("fail_key", failing_work))
        for _ in range(3)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    assert len(results) == 3
    for r in results:
        assert isinstance(r, ValueError)
        assert str(r) == "Upstream exploded"

    assert coalescer.in_flight_count() == 0
