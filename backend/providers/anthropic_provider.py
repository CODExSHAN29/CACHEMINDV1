import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional
import httpx

from backend.app.config import settings
from backend.caching.fingerprint import extract_system_prompt
from backend.normalization.models import NormalizedInferenceRequest
from backend.providers.base import (
    BaseProvider,
    ProviderError,
    ProviderErrorKind,
    ProviderResponse,
    make_safe_provider_message,
)
from backend.routing.model_catalog import resolve_model
from backend.streaming.sse import format_sse_chunk, format_sse_done

logger = logging.getLogger(__name__)


def _normalize_anthropic_error(status_code: int, headers: httpx.Headers, body_text: str) -> ProviderError:
    provider_code: Optional[str] = None
    raw_error_message: str = ""
    try:
        data = json.loads(body_text)
        err = data.get("error", {})
        if isinstance(err, dict):
            provider_code = str(err.get("type") or "") or None
            raw_error_message = str(err.get("message") or "")
    except Exception:
        pass

    retry_after: Optional[float] = None
    retry_header = headers.get("retry-after")
    if retry_header:
        try:
            retry_after = float(retry_header)
        except ValueError:
            pass

    if status_code == 401 or provider_code == "authentication_error":
        kind = ProviderErrorKind.AUTHENTICATION_ERROR
        retryable = False
    elif status_code == 403 or provider_code == "permission_error":
        kind = ProviderErrorKind.PERMISSION_DENIED
        retryable = False
    elif status_code == 404 or provider_code == "not_found_error":
        kind = ProviderErrorKind.NOT_FOUND
        retryable = False
    elif status_code == 429 or provider_code == "rate_limit_error":
        kind = ProviderErrorKind.RATE_LIMIT_EXCEEDED
        retryable = True
    elif status_code in (400, 422) or provider_code == "invalid_request_error":
        lower_check = (raw_error_message + " " + (provider_code or "")).lower()
        if "prompt is too long" in lower_check or "context_length" in lower_check or "max_tokens" in lower_check:
            kind = ProviderErrorKind.CONTEXT_LENGTH_EXCEEDED
        elif "content_filter" in lower_check or "safety" in lower_check:
            kind = ProviderErrorKind.CONTENT_FILTER
        else:
            kind = ProviderErrorKind.INVALID_REQUEST
        retryable = False
    elif status_code in (500, 502, 503, 504, 529) or provider_code == "overloaded_error":
        kind = ProviderErrorKind.UPSTREAM_UNAVAILABLE if status_code in (502, 503, 504, 529) or provider_code == "overloaded_error" else ProviderErrorKind.INTERNAL_SERVER_ERROR
        retryable = True
    else:
        kind = ProviderErrorKind.UNKNOWN
        retryable = (status_code >= 500)

    safe_msg = make_safe_provider_message("anthropic", kind, status_code)

    return ProviderError(
        provider="anthropic",
        kind=kind,
        status_code=status_code,
        provider_code=provider_code,
        retryable=retryable,
        retry_after_seconds=retry_after,
        safe_message=safe_msg,
    )


class AnthropicProvider(BaseProvider):
    """
    Async HTTPX-based provider for Anthropic's Messages API (/v1/messages).
    Translates NormalizedInferenceRequest into Anthropic schema and adapts responses
    back to OpenAI-compatible payloads and SSE streams.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.base_url = (base_url or settings.ANTHROPIC_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.UPSTREAM_TIMEOUT_SECONDS

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout, connect=5.0),
            limits=httpx.Limits(
                max_connections=settings.UPSTREAM_MAX_CONNECTIONS,
                max_keepalive_connections=settings.UPSTREAM_MAX_KEEPALIVE_CONNECTIONS,
            ),
        )

    def _build_headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _transform_request_payload(
        self, request: NormalizedInferenceRequest, stream: bool = False
    ) -> Dict[str, Any]:
        system_prompt = extract_system_prompt(request)
        anthropic_messages: List[Dict[str, Any]] = []

        for msg in request.messages:
            if msg.role == "system":
                continue
            role = "user" if msg.role == "user" else "assistant"
            content = msg.content if isinstance(msg.content, str) else str(msg.content or "")
            if anthropic_messages and anthropic_messages[-1]["role"] == role:
                anthropic_messages[-1]["content"] += f"\n\n{content}"
            else:
                anthropic_messages.append({"role": role, "content": content})

        if not anthropic_messages:
            anthropic_messages.append({"role": "user", "content": "Hello"})

        # Resolve authoritative canonical model
        target = resolve_model(request.model)
        model_name = target.canonical_model

        max_tokens = request.max_tokens if request.max_tokens is not None else 4096

        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        if system_prompt:
            payload["system"] = system_prompt
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p

        return payload

    def _format_anthropic_payload(
        self, request: NormalizedInferenceRequest, stream: bool = False
    ) -> Dict[str, Any]:
        """Formats normalized request into Anthropic messages payload schema."""
        return self._transform_request_payload(request, stream=stream)

    def _translate_anthropic_to_openai(
        self, data: Dict[str, Any], model: str
    ) -> Dict[str, Any]:
        """Translates Anthropic JSON response structure to OpenAI-compatible format."""
        text_content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_content += block.get("text", "")

        usage_data = data.get("usage", {})
        input_tokens = usage_data.get("input_tokens", 0)
        output_tokens = usage_data.get("output_tokens", 0)
        stop_reason = data.get("stop_reason", "end_turn")
        finish_reason = "stop" if stop_reason in ("end_turn", "stop_sequence") else stop_reason

        return {
            "id": data.get("id", f"chatcmpl-ant-{int(time.time())}"),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": data.get("model", model),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": text_content,
                    },
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }

    async def chat_completion(
        self, request: NormalizedInferenceRequest
    ) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError(
                provider="anthropic",
                kind=ProviderErrorKind.CONFIGURATION_ERROR,
                status_code=500,
                retryable=False,
                safe_message="Anthropic upstream API key is not configured.",
            )

        start_time = time.perf_counter_ns()
        payload = self._transform_request_payload(request, stream=False)
        headers = self._build_headers()

        try:
            response = await self._client.post(
                "/messages",
                headers=headers,
                json=payload,
            )
            duration_ms = (time.perf_counter_ns() - start_time) / 1_000_000

            if response.status_code != 200:
                err = _normalize_anthropic_error(response.status_code, response.headers, response.text)
                logger.error("Anthropic upstream error: status=%d kind=%s msg=%s", response.status_code, err.kind.value, err.safe_message)
                raise err

            data = response.json()
            openai_response = self._translate_anthropic_to_openai(data, request.model)
            input_tokens = openai_response["usage"]["prompt_tokens"]
            output_tokens = openai_response["usage"]["completion_tokens"]

            return ProviderResponse(
                raw_response=openai_response,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=data.get("model", request.model),
                provider_latency_ms=duration_ms,
            )
        except httpx.TimeoutException as exc:
            duration_ms = (time.perf_counter_ns() - start_time) / 1_000_000
            logger.error("Anthropic upstream timeout after %.2fms", duration_ms)
            raise ProviderError(
                provider="anthropic",
                kind=ProviderErrorKind.TIMEOUT,
                status_code=504,
                retryable=True,
                safe_message="Anthropic upstream request timed out.",
            ) from exc
        except httpx.RequestError as exc:
            duration_ms = (time.perf_counter_ns() - start_time) / 1_000_000
            logger.error("Anthropic upstream network error: %s", exc)
            raise ProviderError(
                provider="anthropic",
                kind=ProviderErrorKind.NETWORK_ERROR,
                status_code=502,
                retryable=True,
                safe_message=f"Network error communicating with Anthropic: {type(exc).__name__}",
            ) from exc

    async def chat_completion_stream(
        self, request: NormalizedInferenceRequest
    ) -> AsyncIterator[str]:
        if not self.api_key:
            raise ProviderError(
                provider="anthropic",
                kind=ProviderErrorKind.CONFIGURATION_ERROR,
                status_code=500,
                retryable=False,
                safe_message="Anthropic upstream API key is not configured.",
            )

        payload = self._transform_request_payload(request, stream=True)
        headers = self._build_headers()

        request_id = f"chatcmpl-ant-{int(time.time())}"
        model_name = payload["model"]
        created = int(time.time())
        input_tokens = 0
        output_tokens = 0

        # Emit initial role chunk
        yield format_sse_chunk(
            request_id=request_id,
            model=model_name,
            role="assistant",
            content=None,
            created=created,
        )

        try:
            async with self._client.stream("POST", "/messages", headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    err = _normalize_anthropic_error(response.status_code, response.headers, err_body.decode("utf-8", errors="ignore"))
                    logger.error("Anthropic upstream stream error: status=%d kind=%s msg=%s", response.status_code, err.kind.value, err.safe_message)
                    raise err

                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        event_str, buffer = buffer.split("\n\n", 1)
                        lines = event_str.strip().split("\n")
                        event_type = None
                        data_obj = None

                        for line in lines:
                            if line.startswith("event:"):
                                event_type = line[len("event:"):].strip()
                            elif line.startswith("data:"):
                                raw_json = line[len("data:"):].strip()
                                if raw_json and raw_json != "[DONE]":
                                    try:
                                        data_obj = json.loads(raw_json)
                                    except Exception:
                                        data_obj = None

                        if not data_obj:
                            continue

                        if event_type == "message_start":
                            msg = data_obj.get("message", {})
                            if "id" in msg:
                                request_id = f"chatcmpl-{msg['id']}"
                            if "model" in msg:
                                model_name = msg["model"]
                            usage = msg.get("usage", {})
                            input_tokens = usage.get("input_tokens", 0)

                        elif event_type == "content_block_delta":
                            delta = data_obj.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    yield format_sse_chunk(
                                        request_id=request_id,
                                        model=model_name,
                                        content=text,
                                        created=created,
                                    )

                        elif event_type == "message_delta":
                            delta = data_obj.get("delta", {})
                            stop_reason = delta.get("stop_reason", "end_turn")
                            finish_reason = "stop" if stop_reason in ("end_turn", "stop_sequence") else stop_reason
                            usage = data_obj.get("usage", {})
                            output_tokens = usage.get("output_tokens", 0)

                            yield format_sse_chunk(
                                request_id=request_id,
                                model=model_name,
                                finish_reason=finish_reason,
                                usage={
                                    "prompt_tokens": input_tokens,
                                    "completion_tokens": output_tokens,
                                    "total_tokens": input_tokens + output_tokens,
                                },
                                created=created,
                            )

        except httpx.TimeoutException as exc:
            logger.error("Anthropic upstream stream timeout")
            raise ProviderError(
                provider="anthropic",
                kind=ProviderErrorKind.TIMEOUT,
                status_code=504,
                retryable=True,
                safe_message="Anthropic upstream stream request timed out.",
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Anthropic upstream stream network error: %s", exc)
            raise ProviderError(
                provider="anthropic",
                kind=ProviderErrorKind.NETWORK_ERROR,
                status_code=502,
                retryable=True,
                safe_message=f"Network error communicating with Anthropic: {type(exc).__name__}",
            ) from exc

        yield format_sse_done()

    async def close(self) -> None:
        await self._client.aclose()
