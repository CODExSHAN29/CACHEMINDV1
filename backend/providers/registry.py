import logging
from typing import Dict, Optional

from backend.app.config import settings
from backend.providers.anthropic_provider import AnthropicProvider
from backend.providers.base import BaseProvider
from backend.providers.mock_provider import MockProvider
from backend.providers.ollama_provider import OllamaProvider
from backend.providers.openai_provider import OpenAIProvider
from backend.routing.model_catalog import resolve_model

logger = logging.getLogger(__name__)


class ProviderConfigurationError(Exception):
    """Raised when a provider is configured for use but required credentials are missing."""
    pass


def _mocks_allowed() -> bool:
    """Mocks are only allowed when ENVIRONMENT is test, or explicitly via ALLOW_MOCK_PROVIDERS."""
    return settings.ENVIRONMENT == "test" or settings.ALLOW_MOCK_PROVIDERS


class ProviderRegistry:
    """
    Registry for managing and dynamically resolving upstream LLM providers.
    Supports OpenAI, Anthropic, Ollama, and test Mock providers.
    """

    def __init__(self) -> None:
        self._providers: Dict[str, BaseProvider] = {}

    def register(self, name: str, provider: BaseProvider) -> None:
        """Explicitly registers a provider under a specific name."""
        self._providers[name.lower()] = provider

    def get(self, name: str) -> Optional[BaseProvider]:
        """Retrieves a provider by name, creating standard singletons on demand."""
        name_lower = name.lower()
        if name_lower in self._providers:
            return self._providers[name_lower]

        provider: Optional[BaseProvider] = None

        if name_lower == "openai":
            if settings.OPENAI_API_KEY:
                provider = OpenAIProvider()
            elif _mocks_allowed():
                provider = MockProvider(provider_name="openai")
            else:
                raise ProviderConfigurationError(
                    "OPENAI_API_KEY is missing and mock providers are not allowed in production"
                )
        elif name_lower == "anthropic":
            if settings.ANTHROPIC_API_KEY:
                provider = AnthropicProvider()
            elif _mocks_allowed():
                provider = MockProvider(provider_name="anthropic")
            else:
                raise ProviderConfigurationError(
                    "ANTHROPIC_API_KEY is missing and mock providers are not allowed in production"
                )
        elif name_lower == "ollama":
            provider = OllamaProvider()
        elif name_lower == "mock":
            if _mocks_allowed():
                provider = MockProvider(provider_name="mock")
            else:
                raise ProviderConfigurationError("Mock provider is not allowed in production")
        elif "mock" in self._providers:
            return self._providers["mock"]

        if provider is not None:
            self._providers[name_lower] = provider

        return provider

    def resolve_provider_for_model(self, model: str) -> str:
        """
        Determines the appropriate provider name based strictly on authoritative model catalog.
        Fails deterministically with UnknownModelError if model is not recognized.
        """
        target = resolve_model(model)
        return target.provider

    async def close_all(self) -> None:
        """Closes all active provider HTTP clients."""
        for name, provider in list(self._providers.items()):
            try:
                await provider.close()
            except Exception as e:
                logger.warning("Error closing provider %s: %s", name, e)
        self._providers.clear()


_registry_instance: Optional[ProviderRegistry] = None


def get_provider_registry() -> ProviderRegistry:
    """Returns singleton ProviderRegistry."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ProviderRegistry()
    return _registry_instance


def set_provider_registry(registry: ProviderRegistry) -> None:
    """Overrides singleton registry (useful in test harnesses)."""
    global _registry_instance
    _registry_instance = registry
