import json
import httpx
import pytest
from backend.normalization.models import ChatMessage, NormalizedInferenceRequest
from backend.providers.anthropic_provider import AnthropicProvider
from backend.providers.ollama_provider import OllamaProvider
from backend.providers.openai_provider import OpenAIProvider, _build_openai_chat_payload


def test_anthropic_payload_formatting():
    provider = AnthropicProvider(api_key="test_key")
    req = NormalizedInferenceRequest(
        messages=[
            ChatMessage(role="system", content="You are a helpful assistant."),
            ChatMessage(role="user", content="Hello, Claude!"),
        ],
        model="claude-3-5-sonnet-20241022",
        temperature=0.7,
        max_tokens=500,
    )

    payload = provider._format_anthropic_payload(req)
    assert payload["model"] == "claude-3-5-sonnet-20241022"
    assert payload["system"] == "You are a helpful assistant."
    assert len(payload["messages"]) == 1
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["content"] == "Hello, Claude!"
    assert payload["max_tokens"] == 500


def test_anthropic_response_translation():
    provider = AnthropicProvider(api_key="test_key")
    anthropic_raw = {
        "id": "msg_01X",
        "type": "message",
        "role": "assistant",
        "model": "claude-3-5-sonnet-20241022",
        "content": [{"type": "text", "text": "Hello! How can I assist you today?"}],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 15,
            "output_tokens": 20,
        },
    }

    openai_compat = provider._translate_anthropic_to_openai(anthropic_raw, "claude-3-5-sonnet-20241022")
    assert openai_compat["id"] == "msg_01X"
    assert openai_compat["object"] == "chat.completion"
    assert openai_compat["choices"][0]["message"]["content"] == "Hello! How can I assist you today?"
    assert openai_compat["choices"][0]["finish_reason"] == "stop"
    assert openai_compat["usage"]["prompt_tokens"] == 15
    assert openai_compat["usage"]["completion_tokens"] == 20


def test_ollama_payload_formatting():
    provider = OllamaProvider()
    req = NormalizedInferenceRequest(
        messages=[
            ChatMessage(role="user", content="Explain quantum physics in one sentence."),
        ],
        model="llama3",
        temperature=0.2,
        top_p=0.9,
    )

    payload = provider._format_ollama_payload(req)
    assert payload["model"] == "llama3"
    assert len(payload["messages"]) == 1
    assert payload["options"]["temperature"] == 0.2
    assert payload["options"]["top_p"] == 0.9


def test_openai_payload_builder_metadata_stripped():
    req = NormalizedInferenceRequest(
        provider="openai",
        model="gpt-4o",
        messages=[ChatMessage(role="user", content="Hello world")],
        temperature=0.7,
        top_p=0.9,
        n=2,
        seed=42,
        stop=["\n"],
        max_tokens=100,
        max_completion_tokens=100,
        presence_penalty=0.5,
        frequency_penalty=0.5,
        logit_bias={"50256": -100},
        response_format={"type": "json_object"},
        tools=[{"type": "function", "function": {"name": "test_func"}}],
        tool_choice="auto",
        user="test-user-id",
        namespace="tenant-demo",
        tags=["alpha", "beta"],
        attachment_hashes=["hash123"],
        provider_options={"internal": "option_value"},
        client_request_id="req-custom-999",
        allow_provider_fallback=True,
    )

    # 1. Non-streaming payload
    payload = _build_openai_chat_payload(req, stream=False)

    # Excluded metadata check
    for excluded in [
        "provider",
        "namespace",
        "tags",
        "attachment_hashes",
        "provider_options",
        "timeout",
        "client_request_id",
        "allow_provider_fallback",
        "stream",
    ]:
        assert excluded not in payload, f"Metadata '{excluded}' leaked into OpenAI wire payload"

    # Supported parameters check
    assert payload["model"] == "gpt-4o"
    assert payload["messages"] == [{"role": "user", "content": "Hello world"}]
    assert payload["temperature"] == 0.7
    assert payload["top_p"] == 0.9
    assert payload["n"] == 2
    assert payload["seed"] == 42
    assert payload["stop"] == ["\n"]
    assert payload["max_tokens"] == 100
    assert payload["max_completion_tokens"] == 100
    assert payload["presence_penalty"] == 0.5
    assert payload["frequency_penalty"] == 0.5
    assert payload["logit_bias"] == {"50256": -100}
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["tools"] == [{"type": "function", "function": {"name": "test_func"}}]
    assert payload["tool_choice"] == "auto"
    assert payload["user"] == "test-user-id"

    # 2. Streaming payload
    stream_payload = _build_openai_chat_payload(req, stream=True)
    assert stream_payload["stream"] is True
    for excluded in [
        "provider",
        "namespace",
        "tags",
        "attachment_hashes",
        "provider_options",
        "timeout",
        "client_request_id",
        "allow_provider_fallback",
    ]:
        assert excluded not in stream_payload


@pytest.mark.asyncio
async def test_openai_provider_wire_payload_mock_transport():
    captured_requests = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if request.url.path.endswith("/chat/completions"):
            body = {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 123456789,
                "model": "gpt-4o",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello there!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
            return httpx.Response(200, json=body)
        return httpx.Response(404)

    provider = OpenAIProvider(api_key="sk-test-mock-key")
    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(mock_handler),
        base_url="https://api.openai.com/v1",
    )

    req = NormalizedInferenceRequest(
        provider="openai",
        model="gpt-4o",
        messages=[ChatMessage(role="user", content="Ping")],
        namespace="tenant-demo",
        tags=["alpha"],
        attachment_hashes=["abc"],
        provider_options={"internal": "value"},
        client_request_id="req-wire-test",
        allow_provider_fallback=True,
    )

    # 1. Test chat_completion
    resp = await provider.chat_completion(req)
    assert resp.raw_response["choices"][0]["message"]["content"] == "Hello there!"
    assert len(captured_requests) == 1
    sent_payload = json.loads(captured_requests[0].content.decode("utf-8"))
    assert sent_payload["model"] == "gpt-4o"
    assert sent_payload["messages"] == [{"role": "user", "content": "Ping"}]
    for excluded in ["provider", "namespace", "tags", "attachment_hashes", "provider_options", "client_request_id", "allow_provider_fallback"]:
        assert excluded not in sent_payload

    # 2. Test chat_completion_stream
    def mock_stream_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        stream_content = b'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\ndata: [DONE]\n\n'
        return httpx.Response(200, content=stream_content)

    provider._client = httpx.AsyncClient(
        transport=httpx.MockTransport(mock_stream_handler),
        base_url="https://api.openai.com/v1",
    )

    stream_chunks = []
    async for chunk in provider.chat_completion_stream(req):
        stream_chunks.append(chunk)

    assert len(stream_chunks) >= 1
    assert len(captured_requests) == 2
    sent_stream_payload = json.loads(captured_requests[1].content.decode("utf-8"))
    assert sent_stream_payload["stream"] is True
    assert sent_stream_payload["model"] == "gpt-4o"
    for excluded in ["provider", "namespace", "tags", "attachment_hashes", "provider_options", "client_request_id", "allow_provider_fallback"]:
        assert excluded not in sent_stream_payload

    await provider.close()

