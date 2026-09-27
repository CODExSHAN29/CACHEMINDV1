from typing import Any, Dict, List, Optional
import time
from pydantic import BaseModel, ConfigDict, Field

from backend.normalization.models import (
    NormalizedFunctionCall,
    NormalizedInferenceRequest,
    NormalizedMessage,
    NormalizedToolCall,
)


class OpenAIChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    messages: List[Dict[str, Any]]
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Any] = None
    max_tokens: Optional[int] = None
    max_completion_tokens: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    response_format: Optional[Dict[str, Any]] = None
    seed: Optional[int] = None


class OpenAIAdapter:
    @staticmethod
    def parse_request(payload: Dict[str, Any]) -> NormalizedInferenceRequest:
        """Converts an OpenAI-compatible chat completion payload into NormalizedInferenceRequest."""
        req = OpenAIChatCompletionRequest(**payload)

        normalized_messages: List[NormalizedMessage] = []
        for raw_msg in req.messages:
            role = raw_msg.get("role", "user")
            content = raw_msg.get("content")
            name = raw_msg.get("name")
            tool_call_id = raw_msg.get("tool_call_id")

            tool_calls: Optional[List[NormalizedToolCall]] = None
            if "tool_calls" in raw_msg and raw_msg["tool_calls"]:
                tool_calls = []
                for tc in raw_msg["tool_calls"]:
                    fn = tc.get("function", {})
                    tool_calls.append(
                        NormalizedToolCall(
                            id=tc.get("id"),
                            type=tc.get("type", "function"),
                            function=NormalizedFunctionCall(
                                name=fn.get("name", ""),
                                arguments=fn.get("arguments", ""),
                            ),
                        )
                    )

            normalized_messages.append(
                NormalizedMessage(
                    role=role,
                    content=content,
                    name=name,
                    tool_call_id=tool_call_id,
                    tool_calls=tool_calls,
                )
            )

        # Extract extra provider options and cachemind metadata if any
        known_keys = {
            "model", "messages", "tools", "tool_choice", "temperature", "top_p",
            "n", "stream", "stop", "max_tokens", "max_completion_tokens",
            "presence_penalty", "frequency_penalty", "logit_bias", "user",
            "response_format", "seed", "namespace", "tags", "cachemind_namespace", "cachemind_tags"
        }
        provider_options = {k: v for k, v in payload.items() if k not in known_keys}

        namespace = payload.get("namespace") or payload.get("cachemind_namespace")
        raw_tags = payload.get("tags") or payload.get("cachemind_tags") or []
        tags = [str(t).strip() for t in raw_tags if str(t).strip()] if isinstance(raw_tags, list) else []

        return NormalizedInferenceRequest(
            provider="openai",
            model=req.model,
            messages=normalized_messages,
            tools=req.tools,
            tool_choice=req.tool_choice,
            temperature=req.temperature,
            top_p=req.top_p,
            n=req.n,
            seed=req.seed,
            stop=req.stop,
            max_tokens=req.max_tokens,
            max_completion_tokens=req.max_completion_tokens,
            presence_penalty=req.presence_penalty,
            frequency_penalty=req.frequency_penalty,
            logit_bias=req.logit_bias,
            response_format=req.response_format,
            provider_options=provider_options,
            namespace=namespace,
            tags=tags,
            stream=bool(req.stream),
            user=req.user,
        )

    @staticmethod
    def extract_last_user_message(messages: List[Dict[str, Any]]) -> Optional[str]:
        """
        Extract the content of the last user message from a list of messages.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys

        Returns:
            The content of the last user message, or None if no user message found
        """
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content")
        return None

    @staticmethod
    def format_cached_response(
        cached_data: Dict[str, Any],
        request_id: str,
        model: str,
    ) -> Dict[str, Any]:
        """
        Formats a cached response payload to ensure correct OpenAI response envelope
        with standard timestamps and request IDs while preserving original choices & usage.
        """
        response = dict(cached_data)
        response["id"] = f"chatcmpl-{request_id}"
        response["object"] = "chat.completion"
        response["created"] = int(time.time())
        response["model"] = model
        return response
