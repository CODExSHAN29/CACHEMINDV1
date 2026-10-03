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
    "gpt-4o": ResolvedModelTarget("openai", "gpt-4o", ModelCapabilities(tools=True, structured_output=True, multimodal=True, system_instructions=True)),
    "gpt-4o-mini": ResolvedModelTarget("openai", "gpt-4o-mini", ModelCapabilities(tools=True, structured_output=True, multimodal=True, system_instructions=True)),
    "gpt-4-turbo": ResolvedModelTarget("openai", "gpt-4-turbo", ModelCapabilities(tools=True, structured_output=True, multimodal=True, system_instructions=True)),
    "gpt-4": ResolvedModelTarget("openai", "gpt-4", ModelCapabilities(tools=True, structured_output=True, multimodal=False, system_instructions=True)),
    "gpt-3.5-turbo": ResolvedModelTarget("openai", "gpt-3.5-turbo", ModelCapabilities(tools=True, structured_output=True, multimodal=False, system_instructions=True)),
    "o1": ResolvedModelTarget("openai", "o1", ModelCapabilities(tools=False, structured_output=True, multimodal=False, system_instructions=False)),
    "o1-mini": ResolvedModelTarget("openai", "o1-mini", ModelCapabilities(tools=False, structured_output=True, multimodal=False, system_instructions=False)),
    "o1-preview": ResolvedModelTarget("openai", "o1-preview", ModelCapabilities(tools=False, structured_output=True, multimodal=False, system_instructions=False)),
    "o3": ResolvedModelTarget("openai", "o3", ModelCapabilities(tools=True, structured_output=True, multimodal=False, system_instructions=True)),
    "o3-mini": ResolvedModelTarget("openai", "o3-mini", ModelCapabilities(tools=True, structured_output=True, multimodal=False, system_instructions=True)),
    "o4-mini": ResolvedModelTarget("openai", "o4-mini", ModelCapabilities(tools=True, structured_output=True, multimodal=True, system_instructions=True)),

    # Anthropic Models (Adapter currently preserves text & system instructions, no tools, structured_output, or multimodal translation)
    "claude-3-5-sonnet-20241022": ResolvedModelTarget("anthropic", "claude-3-5-sonnet-20241022", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "claude-3-5-sonnet-latest": ResolvedModelTarget("anthropic", "claude-3-5-sonnet-latest", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "claude-3-5-haiku-20241022": ResolvedModelTarget("anthropic", "claude-3-5-haiku-20241022", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "claude-3-5-haiku-latest": ResolvedModelTarget("anthropic", "claude-3-5-haiku-latest", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "claude-3-opus-20240229": ResolvedModelTarget("anthropic", "claude-3-opus-20240229", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "claude-3-opus-latest": ResolvedModelTarget("anthropic", "claude-3-opus-latest", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "claude-3-sonnet-20240229": ResolvedModelTarget("anthropic", "claude-3-sonnet-20240229", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "claude-3-haiku-20240307": ResolvedModelTarget("anthropic", "claude-3-haiku-20240307", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),

    # Ollama / Local Open-Source Models
    "llama3": ResolvedModelTarget("ollama", "llama3", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "llama3.1": ResolvedModelTarget("ollama", "llama3.1", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "llama3.2": ResolvedModelTarget("ollama", "llama3.2", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "mistral": ResolvedModelTarget("ollama", "mistral", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "mixtral": ResolvedModelTarget("ollama", "mixtral", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "qwen2.5": ResolvedModelTarget("ollama", "qwen2.5", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "deepseek-r1": ResolvedModelTarget("ollama", "deepseek-r1", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "deepseek-v3": ResolvedModelTarget("ollama", "deepseek-v3", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "phi4": ResolvedModelTarget("ollama", "phi4", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),
    "gemma2": ResolvedModelTarget("ollama", "gemma2", ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True)),

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

    if m_lower.startswith("o1"):
        return ResolvedModelTarget(
            provider="openai",
            canonical_model=m,
            capabilities=ModelCapabilities(tools=False, structured_output=True, multimodal=False, system_instructions=False),
        )

    if m_lower.startswith("o3") or m_lower.startswith("o4"):
        return ResolvedModelTarget(
            provider="openai",
            canonical_model=m,
            capabilities=ModelCapabilities(tools=True, structured_output=True, multimodal=False, system_instructions=True),
        )

    if m_lower.startswith("gpt-"):
        return ResolvedModelTarget(
            provider="openai",
            canonical_model=m,
            capabilities=ModelCapabilities(tools=True, structured_output=True, multimodal=False, system_instructions=True),
        )

    if m_lower.startswith("claude-"):
        return ResolvedModelTarget(
            provider="anthropic",
            canonical_model=m,
            capabilities=ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True),
        )

    if any(m_lower.startswith(prefix) for prefix in ("llama", "mistral", "mixtral", "deepseek", "phi", "qwen", "gemma")):
        return ResolvedModelTarget(
            provider="ollama",
            canonical_model=m,
            capabilities=ModelCapabilities(tools=False, structured_output=False, multimodal=False, system_instructions=True),
        )

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
