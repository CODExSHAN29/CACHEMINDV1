import pytest
from backend.normalization.models import NormalizedInferenceRequest, NormalizedMessage
from backend.providers.mock_provider import MockProvider


@pytest.mark.asyncio
async def test_mock_provider_call_count_and_synthesis():
    provider = MockProvider()
    assert provider.call_count == 0

    req = NormalizedInferenceRequest(
        model="gpt-4o-mini",
        messages=[NormalizedMessage(role="user", content="What is 2+2?")],
    )

    resp1 = await provider.chat_completion(req)
    assert provider.call_count == 1
    assert "choices" in resp1.raw_response
    assert resp1.model == "gpt-4o-mini"
    assert resp1.input_tokens > 0
    assert resp1.output_tokens > 0

    resp2 = await provider.chat_completion(req)
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_mock_provider_error_modes():
    provider_429 = MockProvider(error_mode="rate_limit_429")
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Hi")],
    )

    with pytest.raises(RuntimeError, match="429"):
        await provider_429.chat_completion(req)
