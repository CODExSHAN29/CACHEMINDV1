import pytest

from backend.guardrails.arbiter import GuardrailArbiter


@pytest.fixture
def arbiter():
    return GuardrailArbiter()


@pytest.mark.asyncio
async def test_guardrail_arbiter_clean_pass(arbiter):
    incoming = "What is the capital of France?"
    candidate = "Tell me the capital of France"
    decision = await arbiter.evaluate(
        incoming_text=incoming,
        candidate_text=candidate,
        incoming_system_prompt="You are a helpful assistant.",
        candidate_system_prompt="You are a helpful assistant.",
    )
    assert decision.passed is True
    assert decision.reason == "PASS"
    assert len(decision.failed_checks) == 0


@pytest.mark.asyncio
async def test_guardrail_arbiter_opposing_actions(arbiter):
    pairs = [
        ("Cancel my monthly subscription", "Renew my monthly subscription"),
        ("Delete the customer database", "Create the customer database"),
        ("Please increase the memory limit", "Please decrease the memory limit"),
        ("I want to buy 100 shares of AAPL", "I want to sell 100 shares of AAPL"),
        ("Approve the pull request", "Reject the pull request"),
        ("Enable dark mode in settings", "Disable dark mode in settings"),
    ]

    for incoming, candidate in pairs:
        decision = await arbiter.evaluate(incoming, candidate)
        assert decision.passed is False, f"Expected rejection for: '{incoming}' vs '{candidate}'"
        assert any("negation" in fc for fc in decision.failed_checks)


@pytest.mark.asyncio
async def test_guardrail_arbiter_negations(arbiter):
    incoming = "I do not want additional insurance"
    candidate = "I do want additional insurance"
    decision = await arbiter.evaluate(incoming, candidate)
    assert decision.passed is False
    assert any("negation" in fc for fc in decision.failed_checks)


@pytest.mark.asyncio
async def test_guardrail_arbiter_numeric_mismatch(arbiter):
    incoming = "Transfer $50 to my checking account"
    candidate = "Transfer $500 to my checking account"
    decision = await arbiter.evaluate(incoming, candidate)
    assert decision.passed is False
    assert any("number" in fc for fc in decision.failed_checks)


@pytest.mark.asyncio
async def test_guardrail_arbiter_numeric_float_normalization(arbiter):
    incoming = "Set temperature to 50.0 degrees"
    candidate = "Set temperature to 50 degrees"
    decision = await arbiter.evaluate(incoming, candidate)
    assert decision.passed is True


@pytest.mark.asyncio
async def test_guardrail_arbiter_date_mismatch(arbiter):
    incoming = "Show me the quarterly revenue for 2020"
    candidate = "Show me the quarterly revenue for 2024"
    decision = await arbiter.evaluate(incoming, candidate)
    assert decision.passed is False
    assert any("date" in fc for fc in decision.failed_checks)


@pytest.mark.asyncio
async def test_guardrail_arbiter_system_prompt_mismatch(arbiter):
    incoming = "Explain photosynthesis"
    candidate = "Explain photosynthesis"
    decision = await arbiter.evaluate(
        incoming_text=incoming,
        candidate_text=candidate,
        incoming_system_prompt="You are a 5 year old child.",
        candidate_system_prompt="You are a university biology professor.",
    )
    assert decision.passed is False
    assert "system_prompt" in decision.failed_checks
