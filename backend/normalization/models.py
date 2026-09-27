from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class NormalizedFunctionCall(BaseModel):
    name: str
    arguments: str


class NormalizedToolCall(BaseModel):
    id: Optional[str] = None
    type: Literal["function"] = "function"
    function: NormalizedFunctionCall


class NormalizedMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool", "function"]
    content: Optional[Union[str, List[Dict[str, Any]]]] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[NormalizedToolCall]] = None


ChatMessage = NormalizedMessage


class NormalizedInferenceRequest(BaseModel):
    """
    Standardized internal representation of an LLM completion request.
    Distinguishes between inference identity attributes (affecting model generation)
    and transport attributes (stream, timeouts, request IDs).
    """
    # Inference Identity Attributes
    provider: str = "openai"
    model: str
    messages: List[NormalizedMessage]
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: Optional[int] = 1
    seed: Optional[int] = None
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    max_completion_tokens: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    logit_bias: Optional[Dict[str, float]] = None
    response_format: Optional[Dict[str, Any]] = None
    attachment_hashes: List[str] = Field(default_factory=list)
    provider_options: Dict[str, Any] = Field(default_factory=dict)
    namespace: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    # Transport / Execution Attributes (Excluded from Exact Cache Identity)
    stream: bool = False
    user: Optional[str] = None
    timeout: Optional[float] = None
    client_request_id: Optional[str] = None

    def to_inference_identity_dict(self) -> Dict[str, Any]:
        """
        Returns a clean dictionary containing ONLY attributes that affect LLM output generation.
        Excludes transport fields (stream, timeout, client_request_id, user).
        """
        data: Dict[str, Any] = {
            "provider": self.provider,
            "model": self.model,
            "messages": [msg.model_dump(exclude_none=True) for msg in self.messages],
        }

        if self.tools is not None:
            data["tools"] = self.tools
        if self.tool_choice is not None:
            data["tool_choice"] = self.tool_choice
        if self.temperature is not None:
            data["temperature"] = self.temperature
        if self.top_p is not None:
            data["top_p"] = self.top_p
        if self.n is not None and self.n != 1:
            data["n"] = self.n
        if self.seed is not None:
            data["seed"] = self.seed
        if self.stop is not None:
            data["stop"] = self.stop
        if self.max_tokens is not None:
            data["max_tokens"] = self.max_tokens
        if self.max_completion_tokens is not None:
            data["max_completion_tokens"] = self.max_completion_tokens
        if self.presence_penalty is not None:
            data["presence_penalty"] = self.presence_penalty
        if self.frequency_penalty is not None:
            data["frequency_penalty"] = self.frequency_penalty
        if self.logit_bias is not None:
            data["logit_bias"] = self.logit_bias
        if self.response_format is not None:
            data["response_format"] = self.response_format
        if self.attachment_hashes:
            data["attachment_hashes"] = sorted(self.attachment_hashes)
        if self.provider_options:
            data["provider_options"] = self.provider_options
        if self.namespace:
            data["namespace"] = self.namespace
        if self.tags:
            data["tags"] = sorted(self.tags)

        return data
