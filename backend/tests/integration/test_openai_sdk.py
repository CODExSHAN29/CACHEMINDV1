import pytest
from httpx import AsyncClient
from openai import AsyncOpenAI

from backend.providers.factory import get_provider


@pytest.mark.asyncio
async def test_openai_sdk_non_streaming_compatibility(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
):
    """
    Verifies that the official OpenAI Python SDK (AsyncOpenAI) can communicate
    seamlessly with CacheMind gateway for standard non-streaming requests.
    """
    raw_key = tenant_a_fixtures["raw_key"]
    provider = get_provider()

    client = AsyncOpenAI(
        api_key=raw_key,
        base_url="http://testserver/v1",
        http_client=async_client,
    )

    # 1. First call -> Cache Miss
    response1 = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Explain map-reduce in distributed systems."}],
        temperature=0.0,
    )

    assert response1.id is not None
    assert response1.model == "gpt-4o"
    assert len(response1.choices) == 1
    assert "Mock response" in response1.choices[0].message.content
    assert provider.call_count == 1

    # 2. Second call -> Cache Hit (0 upstream provider calls)
    response2 = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Explain map-reduce in distributed systems."}],
        temperature=0.0,
    )

    assert response2.choices[0].message.content == response1.choices[0].message.content
    assert provider.call_count == 1  # No extra upstream calls!


@pytest.mark.asyncio
async def test_openai_sdk_streaming_compatibility(
    async_client: AsyncClient,
    tenant_a_fixtures: dict,
):
    """
    Verifies that the official OpenAI Python SDK (AsyncOpenAI) can stream completions
    via CacheMind gateway for both cache misses and cache hits.
    """
    raw_key = tenant_a_fixtures["raw_key"]
    provider = get_provider()

    client = AsyncOpenAI(
        api_key=raw_key,
        base_url="http://testserver/v1",
        http_client=async_client,
    )

    # 1. First streaming call -> Cache Miss
    stream1 = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Generate a quick sorting algorithm in Python"}],
        stream=True,
        temperature=0.0,
    )

    tokens1 = []
    async for chunk in stream1:
        if chunk.choices and chunk.choices[0].delta.content:
            tokens1.append(chunk.choices[0].delta.content)

    full_text_1 = "".join(tokens1)
    assert len(tokens1) >= 2
    assert "Mock response" in full_text_1
    assert provider.call_count == 1

    # 2. Second streaming call -> Cache Hit (0 upstream provider calls)
    stream2 = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Generate a quick sorting algorithm in Python"}],
        stream=True,
        temperature=0.0,
    )

    tokens2 = []
    async for chunk in stream2:
        if chunk.choices and chunk.choices[0].delta.content:
            tokens2.append(chunk.choices[0].delta.content)

    full_text_2 = "".join(tokens2)
    assert full_text_2 == full_text_1
    assert provider.call_count == 1  # Upstream provider call count remains 1
