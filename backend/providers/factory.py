from backend.providers.base import BaseProvider
from backend.providers.registry import get_provider_registry


def get_provider(name: str = "openai") -> BaseProvider:
    """
    Returns upstream provider configured for runtime.
    Defaults to primary provider from the registry.
    """
    registry = get_provider_registry()
    provider = registry.get(name)
    if provider is None:
        provider = registry.get("mock")
    return provider  # type: ignore[return-value]


def set_provider(provider: BaseProvider, name: str = "openai") -> None:
    """Explicitly overrides upstream provider in the registry (used in tests)."""
    registry = get_provider_registry()
    registry.register(name, provider)
