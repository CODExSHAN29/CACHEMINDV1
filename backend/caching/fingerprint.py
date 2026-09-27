import hashlib
from typing import Optional

from backend.normalization.canonicalizer import canonicalize_request, sha256_json
from backend.normalization.models import NormalizedInferenceRequest


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
    model: str,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    namespace: Optional[str] = None,
    tags: Optional[list] = None,
) -> str:
    """
    Computes a scope hash partitioning cache namespaces by tenant, project,
    target model, system prompt, temperature, namespace, and tags.
    """
    scope_data = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "model": model,
        "system_prompt": system_prompt or "",
        "temperature": temperature if temperature is not None else 0.0,
    }
    if namespace:
        scope_data["namespace"] = namespace
    if tags:
        scope_data["tags"] = sorted(tags)
    return sha256_json(scope_data)
