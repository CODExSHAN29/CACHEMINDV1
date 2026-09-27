import pytest
from backend.normalization.models import ChatMessage, NormalizedInferenceRequest
from backend.providers.anthropic_provider import AnthropicProvider
from backend.providers.ollama_provider import OllamaProvider


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
