import pytest
from backend.routing.model_catalog import (
    ModelCapabilities,
    ResolvedModelTarget,
    UnknownModelError,
    is_known_model,
    resolve_model,
)


def test_resolve_known_openai_models():
    target = resolve_model("gpt-4o")
    assert target.provider == "openai"
    assert target.canonical_model == "gpt-4o"
    assert target.capabilities.multimodal is True
    assert target.capabilities.tools is True

    target_mini = resolve_model("gpt-4o-mini")
    assert target_mini.provider == "openai"
    assert target_mini.canonical_model == "gpt-4o-mini"
    assert target_mini.capabilities.multimodal is True

    target_o1 = resolve_model("o1")
    assert target_o1.provider == "openai"
    assert target_o1.canonical_model == "o1"
    assert target_o1.capabilities.tools is False
    assert target_o1.capabilities.system_instructions is False


def test_resolve_known_anthropic_models():
    target = resolve_model("claude-3-5-sonnet-20241022")
    assert target.provider == "anthropic"
    assert target.canonical_model == "claude-3-5-sonnet-20241022"
    assert target.capabilities.multimodal is True

    target_alias = resolve_model("claude-3-5-sonnet-latest")
    assert target_alias.provider == "anthropic"
    assert target_alias.canonical_model == "claude-3-5-sonnet-20241022"

    target_haiku = resolve_model("claude-3-5-haiku-20241022")
    assert target_haiku.provider == "anthropic"
    assert target_haiku.canonical_model == "claude-3-5-haiku-20241022"


def test_resolve_known_ollama_models():
    target_llama = resolve_model("llama3")
    assert target_llama.provider == "ollama"
    assert target_llama.canonical_model == "llama3"

    target_deepseek = resolve_model("deepseek-r1")
    assert target_deepseek.provider == "ollama"
    assert target_deepseek.canonical_model == "deepseek-r1"


def test_resolve_prefix_fallbacks():
    target_custom_gpt = resolve_model("gpt-4-32k-0613")
    assert target_custom_gpt.provider == "openai"
    assert target_custom_gpt.canonical_model == "gpt-4-32k-0613"

    target_custom_claude = resolve_model("claude-3-7-sonnet-20250219")
    assert target_custom_claude.provider == "anthropic"
    assert target_custom_claude.canonical_model == "claude-3-7-sonnet-20250219"

    target_custom_ollama = resolve_model("mistral-small-24b")
    assert target_custom_ollama.provider == "ollama"


def test_resolve_unknown_models_fail_deterministically():
    with pytest.raises(UnknownModelError) as exc_info:
        resolve_model("some-random-unknown-model-xyz")
    assert "some-random-unknown-model-xyz" in str(exc_info.value)
    assert exc_info.value.model_name == "some-random-unknown-model-xyz"

    with pytest.raises(UnknownModelError):
        resolve_model("")

    with pytest.raises(UnknownModelError):
        resolve_model(None)  # type: ignore


def test_unknown_model_with_api_keys_fails_deterministically(monkeypatch):
    from backend.app.config import settings
    from backend.providers.registry import ProviderRegistry

    registry = ProviderRegistry()

    # 1. Unknown model + OpenAI key -> failure
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-proj-test123456789")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    with pytest.raises(UnknownModelError):
        registry.resolve_provider_for_model("unregistered-custom-ai-model")

    # 2. Unknown model + Anthropic key -> failure
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test123456789")
    with pytest.raises(UnknownModelError):
        registry.resolve_provider_for_model("unregistered-custom-ai-model")

    # 3. Unknown model + both keys -> failure
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-proj-test123456789")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test123456789")
    with pytest.raises(UnknownModelError):
        registry.resolve_provider_for_model("unregistered-custom-ai-model")


def test_is_known_model_helper():
    assert is_known_model("gpt-4o") is True
    assert is_known_model("claude-3-5-sonnet-20241022") is True
    assert is_known_model("llama3") is True
    assert is_known_model("mock") is True
    assert is_known_model("unregistered-bogus-model") is False
