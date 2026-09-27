import json
import pytest

from backend.normalization.models import NormalizedInferenceRequest, NormalizedMessage
from backend.providers.mock_provider import MockProvider
from backend.streaming.sse import (
    create_cached_stream_generator,
    format_sse_chunk,
    format_sse_done,
)


def test_format_sse_chunk_role_and_content():
    chunk_str = format_sse_chunk(
        request_id="req-123",
        model="gpt-4o",
        role="assistant",
        content="Hello world",
    )
    assert chunk_str.startswith("data: ")
    assert chunk_str.endswith("\n\n")

    json_str = chunk_str[len("data: "):].strip()
    data = json.loads(json_str)
    assert data["id"] == "req-123"
    assert data["model"] == "gpt-4o"
    assert data["object"] == "chat.completion.chunk"
    assert len(data["choices"]) == 1
    choice = data["choices"][0]
    assert choice["delta"]["role"] == "assistant"
    assert choice["delta"]["content"] == "Hello world"
    assert choice["finish_reason"] is None


def test_format_sse_chunk_finish_reason_and_usage():
    chunk_str = format_sse_chunk(
        request_id="req-123",
        model="gpt-4o",
        finish_reason="stop",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )
    json_str = chunk_str[len("data: "):].strip()
    data = json.loads(json_str)
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["usage"]["total_tokens"] == 15


def test_format_sse_done():
    done_str = format_sse_done()
    assert done_str == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_create_cached_stream_generator():
    cached_payload = {
        "id": "cached-cmpl-1",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "The quick brown fox jumps over the lazy dog",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 8,
            "completion_tokens": 9,
            "total_tokens": 17,
        },
        "system_fingerprint": "fp_test_123",
    }

    chunks = []
    async for chunk in create_cached_stream_generator(cached_payload, "req-stream-1", "gpt-4o", chunk_size=8):
        chunks.append(chunk)

    assert len(chunks) >= 4
    # First chunk should set role
    first_data = json.loads(chunks[0][len("data: "):].strip())
    assert first_data["choices"][0]["delta"]["role"] == "assistant"

    # Middle chunks should contain words
    full_text = ""
    for c in chunks[1:-2]:
        d = json.loads(c[len("data: "):].strip())
        content = d["choices"][0]["delta"].get("content", "")
        full_text += content
    assert full_text == "The quick brown fox jumps over the lazy dog"

    # Penultimate chunk should have finish_reason and usage
    finish_data = json.loads(chunks[-2][len("data: "):].strip())
    assert finish_data["choices"][0]["finish_reason"] == "stop"
    assert finish_data["usage"]["total_tokens"] == 17

    # Last chunk must be [DONE]
    assert chunks[-1] == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_mock_provider_streaming():
    mock = MockProvider()
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Hello stream test")],
        stream=True,
    )

    chunks = []
    async for chunk in mock.chat_completion_stream(req):
        chunks.append(chunk)

    assert mock.call_count == 1
    assert len(chunks) >= 3
    assert chunks[-1] == "data: [DONE]\n\n"
