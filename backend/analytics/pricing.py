from typing import Dict, Tuple


# Upstream LLM Model Pricing: (Input Cost per 1M Tokens, Output Cost per 1M Tokens in USD)
MODEL_PRICING_PER_MILLION: Dict[str, Tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-2024-05-13": (5.00, 15.00),
    "gpt-4o-2024-08-06": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4-turbo-preview": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "gpt-3.5-turbo-0125": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-preview": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o3-mini": (1.10, 4.40),

    # Anthropic
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-sonnet-20240620": (3.00, 15.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus-20240229": (15.00, 75.00),
    "claude-3-opus": (15.00, 75.00),
    "claude-3-sonnet-20240229": (3.00, 15.00),
    "claude-3-haiku-20240307": (0.25, 1.25),

    # Ollama / Self-hosted (Free inference)
    "llama3": (0.0, 0.0),
    "llama3:8b": (0.0, 0.0),
    "llama3:70b": (0.0, 0.0),
    "llama-3.1-8b": (0.0, 0.0),
    "llama-3.1-70b": (0.0, 0.0),
    "mistral": (0.0, 0.0),
    "deepseek-r1": (0.0, 0.0),
    "deepseek-v3": (0.0, 0.0),
    "phi3": (0.0, 0.0),
    "qwen2.5": (0.0, 0.0),
    "gemma2": (0.0, 0.0),

    # Default Mock / Test
    "mock": (0.0, 0.0),
    "mock-gpt-4o": (2.50, 10.00),
}

DEFAULT_MODEL_PRICING: Tuple[float, float] = (2.00, 8.00)


class PricingEngine:
    """
    Calculates estimated financial costs and savings for LLM token usage.
    """

    @classmethod
    def get_model_pricing(cls, model: str) -> Tuple[float, float]:
        """
        Retrieves (input_cost_per_1M, output_cost_per_1M) for a model name.
        Uses prefix matching if exact model name is not found.
        """
        clean_model = model.lower().strip()
        if clean_model in MODEL_PRICING_PER_MILLION:
            return MODEL_PRICING_PER_MILLION[clean_model]

        # Prefix matching
        for key, rates in MODEL_PRICING_PER_MILLION.items():
            if clean_model.startswith(key) or key.startswith(clean_model):
                return rates

        if any(clean_model.startswith(p) for p in ("llama", "mistral", "deepseek", "phi", "qwen", "gemma", "ollama", "mock")):
            return (0.0, 0.0)

        if clean_model.startswith("claude"):
            return (3.00, 15.00)
        elif clean_model.startswith("gpt-4o-mini"):
            return (0.15, 0.60)
        elif clean_model.startswith("gpt-4o"):
            return (2.50, 10.00)
        elif clean_model.startswith("gpt-4"):
            return (10.00, 30.00)

        return DEFAULT_MODEL_PRICING

    @classmethod
    def register_pricing(cls, model: str, input_per_1m: float, output_per_1m: float) -> None:
        """
        Dynamically registers or updates custom model pricing per million tokens.
        """
        MODEL_PRICING_PER_MILLION[model.lower().strip()] = (float(input_per_1m), float(output_per_1m))

    @classmethod
    def calculate_cost(
        cls,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> float:
        """
        Calculates the estimated cost in USD for the given token quantities.
        """
        input_rate, output_rate = cls.get_model_pricing(model)
        input_cost = (max(0, input_tokens) / 1_000_000.0) * input_rate
        output_cost = (max(0, output_tokens) / 1_000_000.0) * output_rate
        return round(input_cost + output_cost, 6)

    @classmethod
    def calculate_savings(
        cls,
        model: str,
        saved_input_tokens: int = 0,
        saved_output_tokens: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> float:
        """
        Calculates the estimated cost saved in USD when a request is served from cache.
        """
        in_tok = max(saved_input_tokens, input_tokens)
        out_tok = max(saved_output_tokens, output_tokens)
        return cls.calculate_cost(model, in_tok, out_tok)
