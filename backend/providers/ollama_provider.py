import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional
import httpx

from backend.app.config import settings
from backend.normalization.models import NormalizedInferenceRequest
from backend.providers.base import (
    BaseProvider,
    ProviderError,
    ProviderErrorKind,
    ProviderResponse,
    make_safe_provider_message,
)
from backend.streaming.sse import format_sse_chunk, format_sse_done

logger = logging.getLogger(__name__)


def _normalize_ollama_error(status_code: int, body_text: str) -> ProviderError:
    if status_code == 404:
        kind = ProviderErrorKind.NOT_FOUND
        retryable = False
    elif status_code in (500, 502, 503, 504):
        kind = ProviderErrorKind.UPSTREAM_UNAVAILABLE if status_code != 500 else ProviderErrorKind.INTERNAL_SERVER_ERROR
        retryable = True
    else:
        kind = ProviderErrorKind.UNKNOWN
        retryable = (status_code >= 500)

    safe_msg = make_safe_provider_message("ollama", kind, status_code)

    return ProviderError(
        provider="ollama",
        kind=kind,
        status_code=status_code,
        retryable=retryable,
        safe_message=safe_msg,
    )


class OllamaProvider(BaseProvider):
    """
    Async HTTPX-based provider for local Ollama instances (/api/chat).
    Translates NormalizedInferenceRequest to Ollama JSON and formats output
    into OpenAI-compatible completions and SSE streams.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.UPSTREAM_TIMEOUT_SECONDS

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout, connect=5.0),
            limits=httpx.Limits(
                max_connections=settings.UPSTREAM_MAX_CONNECTIONS,
                max_keepalive_connections=settings.UPSTREAM_MAX_KEEPALIVE_CONNECTIONS,
            ),
        )

    def _transform_request_payload(
        self, request: NormalizedInferenceRequest, stream: bool = False
    ) -> Dict[str, Any]:
        messages: List[Dict[str, str]] = []
        for msg in request.messages:
            messages.append({
                "role": msg.role,
                "content": msg.content if isinstance(msg.content, str) else str(msg.content or ""),
            })

        options: Dict[str, Any] = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.top_p is not None:
            options["top_p"] = request.top_p
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens

        return {
            "model": request.model,
            "messages": messages,
            "stream": stream,
            "options": options,
        }

    def _format_ollama_payload(
        self, request: NormalizedInferenceRequest, stream: bool = False
    ) -> Dict[str, Any]:
        """Formats normalized request into Ollama REST JSON schema."""
        return self._transform_request_payload(request, stream=stream)

    async def chat_completion(
        self, request: NormalizedInferenceRequest
    ) -> ProviderResponse:
        start_time = time.perf_counter_ns()
        payload = self._transform_request_payload(request, stream=False)

        try:
            response = await self._client.post(
                "/api/chat",
                json=payload,
            )
            duration_ms = (time.perf_counter_ns() - start_time) / 1_000_000

            if response.status_code != 200:
                err = _normalize_ollama_error(response.status_code, response.text)
                logger.error("Ollama upstream error: status=%d kind=%s msg=%s", response.status_code, err.kind.value, err.safe_message)
                raise err

            data = response.json()
            msg = data.get("message", {})
            text_content = msg.get("content", "")
            input_tokens = data.get("prompt_eval_count", 0)
            output_tokens = data.get("eval_count", 0)

            openai_response: Dict[str, Any] = {
                "id": f"chatcmpl-ollama-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": data.get("model", request.model),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": msg.get("role", "assistant"),
                            "content": text_content,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
            }

            return ProviderResponse(
                raw_response=openai_response,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=data.get("model", request.model),
                provider_latency_ms=duration_ms,
            )
        except httpx.TimeoutException as exc:
            duration_ms = (time.perf_counter_ns() - start_time) / 1_000_000
            logger.error("Ollama upstream timeout after %.2fms", duration_ms)
            raise ProviderError(
                provider="ollama",
                kind=ProviderErrorKind.TIMEOUT,
                status_code=504,
                retryable=True,
                safe_message="Ollama upstream request timed out.",
            ) from exc
        except httpx.RequestError as exc:
            duration_ms = (time.perf_counter_ns() - start_time) / 1_000_000
            logger.error("Ollama upstream network error: %s", exc)
            raise ProviderError(
                provider="ollama",
                kind=ProviderErrorKind.NETWORK_ERROR,
                status_code=502,
                retryable=True,
                safe_message=f"Network error communicating with Ollama: {type(exc).__name__}",
            ) from exc

    async def chat_completion_stream(
        self, request: NormalizedInferenceRequest
    ) -> AsyncIterator[str]:
        payload = self._transform_request_payload(request, stream=True)
        request_id = f"chatcmpl-ollama-{int(time.time())}"
        model_name = payload["model"]
        created = int(time.time())

        # 1. Initial role chunk
        yield format_sse_chunk(
            request_id=request_id,
            model=model_name,
            role="assistant",
            content=None,
            created=created,
        )

        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    err = _normalize_ollama_error(response.status_code, err_body.decode("utf-8", errors="ignore"))
                    logger.error("Ollama upstream stream error: status=%d kind=%s msg=%s", response.status_code, err.kind.value, err.safe_message)
                    raise err

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                    except Exception:
                        continue

                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield format_sse_chunk(
                            request_id=request_id,
                            model=model_name,
                            content=content,
                            created=created,
                        )

                    if data.get("done", False):
                        input_tokens = data.get("prompt_eval_count", 0)
                        output_tokens = data.get("eval_count", 0)
                        yield format_sse_chunk(
                            request_id=request_id,
                            model=model_name,
                            finish_reason="stop",
                            usage={
                                "prompt_tokens": input_tokens,
                                "completion_tokens": output_tokens,
                                "total_tokens": input_tokens + output_tokens,
                            },
                            created=created,
                        )
        except httpx.TimeoutException as exc:
            logger.error("Ollama upstream stream timeout")
            raise ProviderError(
                provider="ollama",
                kind=ProviderErrorKind.TIMEOUT,
                status_code=504,
                retryable=True,
                safe_message="Ollama upstream stream request timed out.",
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Ollama upstream stream network error: %s", exc)
            raise ProviderError(
                provider="ollama",
                kind=ProviderErrorKind.NETWORK_ERROR,
                status_code=502,
                retryable=True,
                safe_message=f"Network error communicating with Ollama: {type(exc).__name__}",
            ) from exc

        yield format_sse_done()

    async def close(self) -> None:
        await self._client.aclose()
