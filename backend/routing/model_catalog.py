from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ModelCapabilities:
    streaming: bool = True
    tools: bool = True
    structured_output: bool = True
    multimodal: bool = False
    system_instructions: bool = True


@dataclass(frozen=True)
class ResolvedModelTarget:
    provider: str
    canonical_model: str
    capabilities: ModelCapabilities


class UnknownModelError(Exception):
    def __init__(self, model_name: str) -> None:
        super().__init__(f"Unknown model identifier: '{model_name}'. Provider cannot be inferred.")
        self.model_name = model_name


_MODEL_CATALOG: Dict[str, ResolvedModelTarget] = {
    # OpenAI Models
    "gpt-4o": ResolvedModelTarget("openai", "gpt-4o", ModelCapabilities(multimodal=True)),
    "gpt-4o-mini": ResolvedModelTarget("openai", "gpt-4o-mini", ModelCapabilities(multimodal=True)),
    "gpt-4-turbo": ResolvedModelTarget("openai", "gpt-4-turbo", ModelCapabilities(multimodal=True)),
    "gpt-4": ResolvedModelTarget("openai", "gpt-4", ModelCapabilities(multimodal=False)),
    "gpt-3.5-turbo": ResolvedModelTarget("openai", "gpt-3.5-turbo", ModelCapabilities(multimodal=False)),
    "o1": ResolvedModelTarget("openai", "o1", ModelCapabilities(tools=False, system_instructions=False)),
    "o1-mini": ResolvedModelTarget("openai", "o1-mini", ModelCapabilities(tools=False, system_instructions=False)),
    "o1-preview": ResolvedModelTarget("openai", "o1-preview", ModelCapabilities(tools=False, system_instructions=False)),
    "o3-mini": ResolvedModelTarget("openai", "o3-mini", ModelCapabilities(tools=True)),
    "text-embedding-3-small": ResolvedModelTarget("openai", "text-embedding-3-small", ModelCapabilities(tools=False)),
    "text-embedding-3-large": ResolvedModelTarget("openai", "text-embedding-3-large", ModelCapabilities(tools=False)),
    "text-embedding-ada-002": ResolvedModelTarget("openai", "text-embedding-ada-002", ModelCapabilities(tools=False)),

    # Anthropic Models
    "claude-3-5-sonnet-20241022": ResolvedModelTarget("anthropic", "claude-3-5-sonnet-20241022", ModelCapabilities(multimodal=True)),
    "claude-3-5-sonnet-latest": ResolvedModelTarget("anthropic", "claude-3-5-sonnet-20241022", ModelCapabilities(multimodal=True)),
    "claude-3-5-haiku-20241022": ResolvedModelTarget("anthropic", "claude-3-5-haiku-20241022", ModelCapabilities(multimodal=True)),
    "claude-3-5-haiku-latest": ResolvedModelTarget("anthropic", "claude-3-5-haiku-20241022", ModelCapabilities(multimodal=True)),
    "claude-3-opus-20240229": ResolvedModelTarget("anthropic", "claude-3-opus-20240229", ModelCapabilities(multimodal=True)),
    "claude-3-opus-latest": ResolvedModelTarget("anthropic", "claude-3-opus-20240229", ModelCapabilities(multimodal=True)),
    "claude-3-sonnet-20240229": ResolvedModelTarget("anthropic", "claude-3-sonnet-20240229", ModelCapabilities(multimodal=True)),
    "claude-3-haiku-20240307": ResolvedModelTarget("anthropic", "claude-3-haiku-20240307", ModelCapabilities(multimodal=True)),

    # Ollama / Local Open-Source Models
    "llama3": ResolvedModelTarget("ollama", "llama3", ModelCapabilities()),
    "llama3.1": ResolvedModelTarget("ollama", "llama3.1", ModelCapabilities()),
    "llama3.2": ResolvedModelTarget("ollama", "llama3.2", ModelCapabilities(multimodal=True)),
    "mistral": ResolvedModelTarget("ollama", "mistral", ModelCapabilities()),
    "mixtral": ResolvedModelTarget("ollama", "mixtral", ModelCapabilities()),
    "qwen2.5": ResolvedModelTarget("ollama", "qwen2.5", ModelCapabilities()),
    "deepseek-r1": ResolvedModelTarget("ollama", "deepseek-r1", ModelCapabilities()),
    "deepseek-v3": ResolvedModelTarget("ollama", "deepseek-v3", ModelCapabilities()),
    "phi4": ResolvedModelTarget("ollama", "phi4", ModelCapabilities()),
    "gemma2": ResolvedModelTarget("ollama", "gemma2", ModelCapabilities()),

    # Mock Test Models
    "mock": ResolvedModelTarget("mock", "mock-model", ModelCapabilities()),
    "mock-model": ResolvedModelTarget("mock", "mock-model", ModelCapabilities()),
}


def resolve_model(model_name: str) -> ResolvedModelTarget:
    """
    Authoritative resolution of model names to canonical provider targets and capabilities.
    Only place allowed to infer providers from model names.
    Raises UnknownModelError if model cannot be resolved deterministically.
    """
    if not model_name or not isinstance(model_name, str):
        raise UnknownModelError(str(model_name))

    m = model_name.strip()
    m_lower = m.lower()

    if m_lower in _MODEL_CATALOG:
        return _MODEL_CATALOG[m_lower]

    if m_lower.startswith("gpt-") or m_lower.startswith("o1") or m_lower.startswith("o3") or m_lower.startswith("text-embedding-"):
        return ResolvedModelTarget(provider="openai", canonical_model=m, capabilities=ModelCapabilities())

    if m_lower.startswith("claude-"):
        return ResolvedModelTarget(provider="anthropic", canonical_model=m, capabilities=ModelCapabilities(multimodal=True))

    if any(m_lower.startswith(prefix) for prefix in ("llama", "mistral", "mixtral", "deepseek", "phi", "qwen", "gemma")):
        return ResolvedModelTarget(provider="ollama", canonical_model=m, capabilities=ModelCapabilities())

    if m_lower.startswith("mock"):
        return ResolvedModelTarget(provider="mock", canonical_model=m, capabilities=ModelCapabilities())

    raise UnknownModelError(model_name)


def is_known_model(model_name: str) -> bool:
    """Returns True if the model identifier can be resolved to a provider."""
    try:
        resolve_model(model_name)
        return True
    except UnknownModelError:
        return False
