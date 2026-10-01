import asyncio
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.providers.factory import get_provider


@pytest.mark.asyncio
async def test_single_flight_coalescing_high_concurrency_proof(
    async_client: AsyncClient,
    db_session: AsyncSession,
    tenant_a_fixtures: dict,
):
    """
    Scientifically proves single-flight request coalescing under high concurrency (50 requests):
    - 50 simultaneous identical requests hit a cold cache.
    - Simulated upstream latency is set to 30ms to reflect realistic network round-trips.
    - Exactly 1 leader dispatches to the upstream LLM.
    - Exactly 49 followers are coalesced onto the leader's future with X-CacheMind-Coalesced: true.
    - Upstream provider call count increases by exactly 1.
    """
    raw_key = tenant_a_fixtures["raw_key"]
    headers = {"Authorization": f"Bearer {raw_key}", "Content-Type": "application/json"}
    provider = get_provider()
    provider.simulated_latency_ms = 30.0

    initial_provider_calls = provider.call_count
    concurrency = 50

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Explain zero-copy networking in Linux in detail."}],
        "temperature": 0.0,
    }

    start_barrier = asyncio.Event()

    async def single_request(idx: int):
        await start_barrier.wait()
        return await async_client.post("/v1/chat/completions", headers=headers, json=payload)

    tasks = [asyncio.create_task(single_request(i)) for i in range(concurrency)]

    # Release all 50 coroutines in the same event loop tick
    start_barrier.set()
    responses = await asyncio.gather(*tasks)

    # Reset simulated latency
    provider.simulated_latency_ms = 0.0

    assert len(responses) == concurrency
    for r in responses:
        assert r.status_code == 200

    coalesced_followers = [r for r in responses if r.headers.get("X-CacheMind-Coalesced", "false").lower() == "true"]
    leaders = [r for r in responses if r.headers.get("X-CacheMind-Coalesced", "false").lower() != "true"]

    # Exactly 1 leader, 49 coalesced followers
    assert len(leaders) == 1
    assert len(coalesced_followers) == concurrency - 1

    # Exactly 1 upstream call made
    assert provider.call_count == initial_provider_calls + 1

    # Leader was a cache MISS, followers got the exact same content
    leader_content = leaders[0].json()["choices"][0]["message"]["content"]
    for follower in coalesced_followers:
        assert follower.json()["choices"][0]["message"]["content"] == leader_content
