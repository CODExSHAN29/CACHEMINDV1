import time
from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from backend.auth.dependencies import get_authenticated_identity
from backend.auth.identity import AuthenticatedIdentity

router = APIRouter(prefix="/v1", tags=["Models"])

AVAILABLE_MODELS = [
    {"id": "gpt-4o", "object": "model", "created": 1715367049, "owned_by": "openai"},
    {"id": "gpt-4o-mini", "object": "model", "created": 1721260800, "owned_by": "openai"},
    {"id": "gpt-4-turbo", "object": "model", "created": 1712361441, "owned_by": "openai"},
    {"id": "gpt-3.5-turbo", "object": "model", "created": 1677610602, "owned_by": "openai"},
    {"id": "claude-3-5-sonnet-20241022", "object": "model", "created": 1729555200, "owned_by": "anthropic"},
    {"id": "claude-3-5-haiku-20241022", "object": "model", "created": 1729555200, "owned_by": "anthropic"},
]


@router.get("/models")
async def list_models(
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
) -> Dict[str, Any]:
    """Returns available models compatible with the OpenAI API format."""
    return {
        "object": "list",
        "data": AVAILABLE_MODELS,
    }
