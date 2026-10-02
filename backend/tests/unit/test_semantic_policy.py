import pytest

from backend.normalization.models import (
    NormalizedInferenceRequest,
    NormalizedMessage,
)
from backend.semantic.policy import (
    SemanticEligibility,
    SemanticPolicyReason,
    evaluate_semantic_eligibility,
)


def test_single_turn_user_only_is_eligible():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Hello, what is CacheMind?")],
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is True
    assert result.reason == SemanticPolicyReason.OK


def test_single_turn_with_system_prompt_is_eligible():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[
            NormalizedMessage(role="system", content="You are a helpful assistant."),
            NormalizedMessage(role="user", content="Explain quantum computing."),
        ],
        temperature=0.0,
        top_p=1.0,
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is True
    assert result.reason == SemanticPolicyReason.OK


def test_no_user_message_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="system", content="System only")],
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.NO_USER_MESSAGE


def test_multiple_user_messages_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[
            NormalizedMessage(role="user", content="First question"),
            NormalizedMessage(role="user", content="Second question"),
        ],
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.MULTIPLE_USER_MESSAGES


def test_assistant_message_present_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[
            NormalizedMessage(role="user", content="Hello"),
            NormalizedMessage(role="assistant", content="Hi there!"),
        ],
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.ASSISTANT_MESSAGE_PRESENT


def test_tool_message_present_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[
            NormalizedMessage(role="user", content="Search query"),
            NormalizedMessage(role="tool", content="Tool search result", tool_call_id="call_1"),
        ],
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.TOOL_MESSAGE_PRESENT


def test_function_message_present_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[
            NormalizedMessage(role="user", content="Compute sum"),
            NormalizedMessage(role="function", content="42", name="sum_fn"),
        ],
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.FUNCTION_MESSAGE_PRESENT


def test_multiple_system_messages_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[
            NormalizedMessage(role="system", content="System instruction 1"),
            NormalizedMessage(role="system", content="System instruction 2"),
            NormalizedMessage(role="user", content="User prompt"),
        ],
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.MULTI_TURN_HISTORY


def test_tool_definitions_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="What's the weather?")],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather",
                    "parameters": {"type": "object", "properties": {"loc": {"type": "string"}}},
                },
            }
        ],
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.TOOL_DEFINITIONS_PRESENT


def test_tool_choice_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="What's the weather?")],
        tool_choice="auto",
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.TOOL_CHOICE_PRESENT


def test_response_format_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Return JSON user object")],
        response_format={"type": "json_object"},
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.STRUCTURED_OUTPUT_SCHEMA


def test_multimodal_content_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[
            NormalizedMessage(
                role="user",
                content=[
                    {"type": "text", "text": "What is in this image?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/cat.jpg"}},
                ],
            )
        ],
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.MULTIMODAL_CONTENT


def test_non_default_temperature_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Write a creative poem")],
        temperature=0.7,
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS


def test_non_default_top_p_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Translate this text")],
        top_p=0.5,
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS


def test_non_default_max_tokens_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Summarize article")],
        max_tokens=150,
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS


def test_non_default_n_completions_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Brainstorm 5 names")],
        n=3,
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS


def test_non_default_seed_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Deterministic query")],
        seed=12345,
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS


def test_non_default_stop_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Generate code")],
        stop=["###", "```"],
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS


def test_non_default_penalties_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Essay")],
        presence_penalty=0.5,
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS

    req2 = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Essay")],
        frequency_penalty=0.5,
    )
    result2 = evaluate_semantic_eligibility(req2)
    assert result2.eligible is False
    assert result2.reason == SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS


def test_attachment_hashes_rejected():
    req = NormalizedInferenceRequest(
        model="gpt-4o",
        messages=[NormalizedMessage(role="user", content="Analyze uploaded doc")],
        attachment_hashes=["hash_abc123"],
    )
    result = evaluate_semantic_eligibility(req)
    assert result.eligible is False
    assert result.reason == SemanticPolicyReason.ATTACHMENTS_PRESENT
