from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class CacheTelemetry(BaseModel):
    status: Literal["EXACT_HIT", "SEMANTIC_HIT", "CACHE_MISS"] = "CACHE_MISS"
    similarity_score: Optional[float] = None
    tokens_saved: int = 0
    cost_saved_usd: float = 0.0
    latency_ms: float = 0.0


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Optional[UsageInfo] = None
    cachemind: CacheTelemetry = Field(default_factory=CacheTelemetry)


class PurgeResult(BaseModel):
    exact_keys_removed: int
    semantic_vectors_removed: int


class WarmResult(BaseModel):
    seeded: int
