import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from backend.app.config import settings
from backend.caching.factory import get_cache_backend
from backend.caching.fingerprint import compute_exact_request_hash, compute_scope_hash, extract_system_prompt
from backend.caching.models import CachedResponse
from backend.normalization.models import NormalizedInferenceRequest, NormalizedMessage
from backend.semantic.factory import get_semantic_cache_service
from backend.semantic.policy import evaluate_semantic_eligibility

logger = logging.getLogger(__name__)


class WarmItem(BaseModel):
    prompt: Union[str, List[Dict[str, Any]]] = Field(
        ...,
        description="Prompt string or list of OpenAI message dicts ({'role': 'user', 'content': '...'})"
    )
    completion: Optional[str] = Field(default=None, description="Alias for response text")
    response: Optional[str] = Field(default=None, description="The authoritative pre-computed completion text")
    model: str = Field(default="gpt-4o", description="Target model name")
    provider: str = Field(default="openai", description="Target provider name")
    system_prompt: Optional[str] = Field(default=None, description="Optional system prompt")
    temperature: float = Field(default=0.0, description="Temperature setting (default 0.0)")
    namespace: Optional[str] = Field(default=None, description="Optional semantic namespace")
    tags: List[str] = Field(default_factory=list, description="Optional categorization tags")
    ttl_seconds: int = Field(default=86400, description="Cache TTL in seconds (default 24h)")


class WarmBatchRequest(BaseModel):
    items: List[WarmItem] = Field(..., description="List of pre-warming prompt-response pairs")
    tenant_id: Optional[str] = Field(default=None, description="Target tenant ID (admin-only override)")
    project_id: Optional[str] = Field(default=None, description="Target project ID (defaults to authenticated project)")


class WarmBatchResult(BaseModel):
    tenant_id: str
    project_id: str
    total_items: int = 0
    exact_seeded: int = 0
    semantic_seeded: int = 0
    seeded_count: int = 0
    failed_count: int = 0
    exact_hashes: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class CacheWarmer:
    """
    Cache Pre-Warming / Seeding Engine.
    Pre-populates L1 Exact Cache and L2 Semantic Vector Index with pre-computed
    Q&A pairs, FAQ embeddings, or system documentation for instant zero-latency hits.
    """

    @classmethod
    async def warm_cache(
        cls,
        tenant_id: str,
        project_id: str,
        items: List[WarmItem],
    ) -> WarmBatchResult:
        cache_backend = get_cache_backend()
        semantic_service = get_semantic_cache_service()

        exact_seeded = 0
        semantic_seeded = 0
        failed_count = 0
        exact_hashes: List[str] = []
        errors: List[str] = []

        for idx, item in enumerate(items):
            try:
                # 1. Normalize Messages
                messages: List[NormalizedMessage] = []
                if item.system_prompt:
                    messages.append(NormalizedMessage(role="system", content=item.system_prompt))

                if isinstance(item.prompt, str):
                    messages.append(NormalizedMessage(role="user", content=item.prompt))
                    last_user_text = item.prompt
                elif isinstance(item.prompt, list):
                    for m in item.prompt:
                        role = m.get("role", "user")
                        content = m.get("content", "")
                        messages.append(NormalizedMessage(role=role, content=content))
                    # Find last user text
                    user_msgs = [m.content for m in messages if m.role == "user" and isinstance(m.content, str)]
                    last_user_text = user_msgs[-1] if user_msgs else ""
                else:
                    last_user_text = str(item.prompt)
                    messages.append(NormalizedMessage(role="user", content=last_user_text))

                norm_req = NormalizedInferenceRequest(
                    provider=item.provider,
                    model=item.model,
                    messages=messages,
                    temperature=item.temperature,
                    stream=False,
                    namespace=item.namespace,
                    tags=item.tags,
                )

                # 2. Derive Exact Hash & Scope Hash
                exact_hash = compute_exact_request_hash(tenant_id, project_id, norm_req)
                sys_prompt = extract_system_prompt(norm_req)
                scope_hash = compute_scope_hash(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    provider=norm_req.provider,
                    model=norm_req.model,
                    system_prompt=sys_prompt,
                    temperature=norm_req.temperature,
                    namespace=norm_req.namespace,
                    tags=norm_req.tags,
                    top_p=norm_req.top_p,
                    max_tokens=norm_req.max_tokens,
                    max_completion_tokens=norm_req.max_completion_tokens,
                    presence_penalty=norm_req.presence_penalty,
                    frequency_penalty=norm_req.frequency_penalty,
                    seed=norm_req.seed,
                    stop=norm_req.stop,
                    response_format=norm_req.response_format,
                    tools=norm_req.tools,
                    tool_choice=norm_req.tool_choice,
                )

                # 3. Build Canonical Response Dict
                resolved_content = item.response or getattr(item, "completion", None) or getattr(item, "response_text", "") or ""
                in_tokens = max(1, len(last_user_text) // 4 + 4)
                out_tokens = max(1, len(resolved_content) // 4 + 1)
                req_id = f"cm-warm-{uuid.uuid4().hex[:12]}"

                raw_response: Dict[str, Any] = {
                    "id": req_id,
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": item.model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": resolved_content,
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": in_tokens,
                        "completion_tokens": out_tokens,
                        "total_tokens": in_tokens + out_tokens,
                    },
                }

                # 4. L1 Exact Cache Set
                cached_entry = CachedResponse(
                    exact_request_hash=exact_hash,
                    response_payload=raw_response,
                    provider=item.provider,
                    model=item.model,
                    content=resolved_content,
                    ttl_seconds=item.ttl_seconds,
                    namespace=item.namespace,
                    tags=item.tags,
                )
                await cache_backend.set(
                    project_id=project_id,
                    exact_request_hash=exact_hash,
                    payload=cached_entry,
                    ttl_seconds=item.ttl_seconds,
                )
                exact_seeded += 1

                # 5. L2 Semantic Cache Insert (Opt-in and fail-closed)
                if settings.SEMANTIC_CACHE_MODE == "safe" and last_user_text:
                    eligibility = evaluate_semantic_eligibility(norm_req)
                    if eligibility.eligible:
                        query_vector = await semantic_service.embedding_engine.embed(last_user_text)
                        semantic_payload = dict(raw_response)
                        semantic_payload["__cachemind_input_text__"] = last_user_text
                        semantic_payload["__cachemind_system_prompt__"] = sys_prompt

                        await semantic_service.backend.insert(
                            scope_hash=scope_hash,
                            exact_request_hash=exact_hash,
                            vector=query_vector,
                            response_payload=semantic_payload,
                            created_at=time.time(),
                            input_text=last_user_text,
                            system_prompt=sys_prompt,
                            provider=item.provider,
                            model=item.model,
                            ttl_seconds=item.ttl_seconds,
                            tenant_id=tenant_id,
                            project_id=project_id,
                            namespace=item.namespace,
                            tags=item.tags,
                        )
                        semantic_seeded += 1

                exact_hashes.append(exact_hash)

            except Exception as exc:
                failed_count += 1
                err_msg = f"Item #{idx} failed to warm: {str(exc)}"
                logger.error(err_msg)
                errors.append(err_msg)

        return WarmBatchResult(
            tenant_id=tenant_id,
            project_id=project_id,
            total_items=len(items),
            exact_seeded=exact_seeded,
            semantic_seeded=semantic_seeded,
            seeded_count=exact_seeded,
            failed_count=failed_count,
            exact_hashes=exact_hashes,
            errors=errors,
        )
