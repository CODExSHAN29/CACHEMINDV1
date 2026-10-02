import hashlib
from typing import Any, Dict, List, Optional

from backend.normalization.canonicalizer import canonicalize_request, sha256_json
from backend.normalization.models import NormalizedInferenceRequest

SEMANTIC_POLICY_VERSION = "v2"


def extract_system_prompt(request: NormalizedInferenceRequest) -> Optional[str]:
    """Extracts the first system message content if present."""
    for msg in request.messages:
        if msg.role == "system" and isinstance(msg.content, str):
            return msg.content
    return None


def compute_exact_request_hash(
    tenant_id: str, project_id: str, request: NormalizedInferenceRequest
) -> str:
    """
    Computes a cryptographic exact request hash binding tenant identity,
    project identity, and canonicalized inference payload.
    """
    canonical_body = canonicalize_request(request)
    composite = f"tenant:{tenant_id}|proj:{project_id}|body:{canonical_body}"
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()


def compute_scope_hash(
    tenant_id: str,
    project_id: str,
    provider: str,
    model: str,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    namespace: Optional[str] = None,
    tags: Optional[List[str]] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    max_completion_tokens: Optional[int] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    seed: Optional[int] = None,
    stop: Optional[Any] = None,
    response_format: Optional[Any] = None,
    tools: Optional[Any] = None,
    tool_choice: Optional[Any] = None,
    policy_version: str = SEMANTIC_POLICY_VERSION,
) -> str:
    """
    Computes a scope hash partitioning cache namespaces by tenant, project,
    provider, target model, system prompt, generation parameters, execution contract,
    namespace, tags, and semantic policy version.
    """
    scope_data: Dict[str, Any] = {
        "policy_version": policy_version,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "provider": provider,
        "model": model,
        "system_prompt": system_prompt or "",
        "temperature": temperature if temperature is not None else 1.0,
    }
    if top_p is not None:
        scope_data["top_p"] = top_p
    if max_tokens is not None:
        scope_data["max_tokens"] = max_tokens
    if max_completion_tokens is not None:
        scope_data["max_completion_tokens"] = max_completion_tokens
    if presence_penalty is not None:
        scope_data["presence_penalty"] = presence_penalty
    if frequency_penalty is not None:
        scope_data["frequency_penalty"] = frequency_penalty
    if seed is not None:
        scope_data["seed"] = seed
    if stop is not None:
        scope_data["stop"] = stop
    if response_format is not None:
        scope_data["response_format"] = response_format
    if tools is not None:
        scope_data["tools"] = tools
    if tool_choice is not None:
        scope_data["tool_choice"] = tool_choice
    if namespace:
        scope_data["namespace"] = namespace
    if tags:
        scope_data["tags"] = sorted(tags)
    return sha256_json(scope_data)
