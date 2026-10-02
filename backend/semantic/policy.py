"""Centralized, fail-closed semantic eligibility policy for L2 vector cache.

Only single-turn plain-text requests may use L2 lookup/insertion.
Everything else fails closed (eligible=False) to prevent cross-conversation
pollution and invalid reuse.
"""
from enum import Enum
from typing import Optional

from backend.normalization.models import NormalizedInferenceRequest


class SemanticPolicyReason(Enum):
    OK = "ok"
    MULTI_TURN_HISTORY = "multi_turn_history"
    ASSISTANT_MESSAGE_PRESENT = "assistant_message_present"
    TOOL_MESSAGE_PRESENT = "tool_message_present"
    FUNCTION_MESSAGE_PRESENT = "function_message_present"
    TOOL_DEFINITIONS_PRESENT = "tool_definitions_present"
    TOOL_CHOICE_PRESENT = "tool_choice_present"
    STRUCTURED_OUTPUT_SCHEMA = "structured_output_schema"
    MULTIMODAL_CONTENT = "multimodal_content"
    NON_DEFAULT_GENERATION_PARAMS = "non_default_generation_params"
    ATTACHMENTS_PRESENT = "attachments_present"
    NO_USER_MESSAGE = "no_user_message"
    MULTIPLE_USER_MESSAGES = "multiple_user_messages"


class SemanticEligibility:
    eligible: bool
    reason: SemanticPolicyReason

    def __init__(self, eligible: bool, reason: SemanticPolicyReason = SemanticPolicyReason.OK) -> None:
        self.eligible = eligible
        self.reason = reason


def evaluate_semantic_eligibility(req: NormalizedInferenceRequest) -> SemanticEligibility:
    """Fail-closed evaluation. Returns eligible=True ONLY when request is
    exactly one system message (optional) and exactly one user message,
    with no assistant/tool/function messages, no tool definitions, no
    structured response_format, no multimodal content parts, and only
    default generation parameters."""
    messages = req.messages or []

    # Must have exactly one user message
    user_msgs = [m for m in messages if m.role == "user"]
    if len(user_msgs) != 1:
        if len(user_msgs) == 0:
            return SemanticEligibility(False, SemanticPolicyReason.NO_USER_MESSAGE)
        return SemanticEligibility(False, SemanticPolicyReason.MULTIPLE_USER_MESSAGES)

    # No assistant messages
    if any(m.role == "assistant" for m in messages):
        return SemanticEligibility(False, SemanticPolicyReason.ASSISTANT_MESSAGE_PRESENT)

    # No tool or function messages
    if any(m.role == "tool" for m in messages):
        return SemanticEligibility(False, SemanticPolicyReason.TOOL_MESSAGE_PRESENT)
    if any(m.role == "function" for m in messages):
        return SemanticEligibility(False, SemanticPolicyReason.FUNCTION_MESSAGE_PRESENT)

    # At most one system message (optional)
    sys_msgs = [m for m in messages if m.role == "system"]
    if len(sys_msgs) > 1:
        return SemanticEligibility(False, SemanticPolicyReason.MULTI_TURN_HISTORY)

    # Total message count check: system (<=1) + user (1) = <=2, and only those roles
    allowed = {"system", "user"}
    for m in messages:
        if m.role not in allowed:
            # Any other role caught above; defensive
            return SemanticEligibility(False, SemanticPolicyReason.MULTI_TURN_HISTORY)
    if len(messages) > 2:
        return SemanticEligibility(False, SemanticPolicyReason.MULTI_TURN_HISTORY)

    # No tool/function definitions
    if req.tools is not None and len(req.tools) > 0:
        return SemanticEligibility(False, SemanticPolicyReason.TOOL_DEFINITIONS_PRESENT)
    if req.tool_choice is not None:
        return SemanticEligibility(False, SemanticPolicyReason.TOOL_CHOICE_PRESENT)

    # No structured JSON output constraints
    if req.response_format is not None:
        return SemanticEligibility(False, SemanticPolicyReason.STRUCTURED_OUTPUT_SCHEMA)

    # No multimodal content parts
    for m in messages:
        content = m.content
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") in ("image_url", "image", "file"):
                    return SemanticEligibility(False, SemanticPolicyReason.MULTIMODAL_CONTENT)

    # Only default/deterministic generation parameters permitted for L2 eligibility
    # Defaults: temperature in (0.0, 1.0) or None, top_p=1.0 or None, max_tokens=None, etc.
    # Any explicit non-deterministic or restrictive deviation is ineligible.
    if req.temperature is not None and not (abs(req.temperature) < 1e-6 or abs(req.temperature - 1.0) < 1e-6):
        return SemanticEligibility(False, SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS)
    if req.top_p is not None and abs(req.top_p - 1.0) > 1e-6:
        return SemanticEligibility(False, SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS)
    if req.max_tokens is not None:
        return SemanticEligibility(False, SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS)
    if req.max_completion_tokens is not None:
        return SemanticEligibility(False, SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS)
    if req.n is not None and req.n != 1:
        return SemanticEligibility(False, SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS)
    if req.seed is not None:
        return SemanticEligibility(False, SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS)
    if req.stop is not None:
        return SemanticEligibility(False, SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS)
    if req.presence_penalty is not None and abs(req.presence_penalty) > 1e-6:
        return SemanticEligibility(False, SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS)
    if req.frequency_penalty is not None and abs(req.frequency_penalty) > 1e-6:
        return SemanticEligibility(False, SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS)
    if req.logit_bias is not None and len(req.logit_bias) > 0:
        return SemanticEligibility(False, SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS)
    if req.provider_options:
        return SemanticEligibility(False, SemanticPolicyReason.NON_DEFAULT_GENERATION_PARAMS)

    # No attachments
    if req.attachment_hashes:
        return SemanticEligibility(False, SemanticPolicyReason.ATTACHMENTS_PRESENT)

    return SemanticEligibility(True, SemanticPolicyReason.OK)
