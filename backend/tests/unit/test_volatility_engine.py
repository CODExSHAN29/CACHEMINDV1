import pytest

from backend.guardrails.volatility import VolatilityEngine, VolatilityTier


@pytest.fixture
def engine():
    return VolatilityEngine()


@pytest.mark.asyncio
async def test_volatility_volatile_queries(engine):
    volatile_prompts = [
        "What is the current stock price of TSLA?",
        "Show me the live score for the Lakers game",
        "What is the bitcoin price right now in USD?",
        "Check flight status for UA123 today",
    ]

    for prompt in volatile_prompts:
        result = await engine.classify(prompt)
        assert result.tier == VolatilityTier.VOLATILE, f"Prompt failed: {prompt}"
        assert result.ttl_seconds == 300


@pytest.mark.asyncio
async def test_volatility_semi_static_queries(engine):
    semi_static_prompts = [
        "Give me a movie review of Inception",
        "What are the latest customer reviews for iPhone 15?",
        "Show me the quarterly earnings summary for Microsoft",
    ]

    for prompt in semi_static_prompts:
        result = await engine.classify(prompt)
        assert result.tier == VolatilityTier.SEMI_STATIC, f"Prompt failed: {prompt}"
        assert result.ttl_seconds == 86400


@pytest.mark.asyncio
async def test_volatility_evergreen_queries(engine):
    evergreen_prompts = [
        "How to sort an array in Python tutorial",
        "What is the definition of polymorphism in computer science?",
        "Explain the history of the Roman Empire",
        "What is the formula for calculating kinetic energy?",
    ]

    for prompt in evergreen_prompts:
        result = await engine.classify(prompt)
        assert result.tier == VolatilityTier.EVERGREEN, f"Prompt failed: {prompt}"
        assert result.ttl_seconds == 2592000


@pytest.mark.asyncio
async def test_volatility_get_ttl(engine):
    ttl = await engine.get_ttl("Stock price of Apple")
    assert ttl == 300

    ttl_evergreen = await engine.get_ttl("How to cook rice tutorial")
    assert ttl_evergreen == 2592000
