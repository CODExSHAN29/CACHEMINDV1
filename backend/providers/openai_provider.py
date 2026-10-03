import json
import logging
import time
from typing import Any, AsyncIterator, Dict, Optional
import httpx

from backend.app.config import settings
from backend.normalization.models import NormalizedInferenceRequest
from backend.providers.base import BaseProvider, ProviderError, ProviderErrorKind, ProviderResponse

logger = logging.getLogger(__name__)


def _normalize_openai_error(status_code: int, headers: httpx.Headers, body_text: str) -> ProviderError:
    provider_code: Optional[str] = None
    safe_msg = f"OpenAI upstream returned HTTP {status_code}."
    try:
        data = json.loads(body_text)
        err = data.get("error", {})
        if isinstance(err, dict):
            provider_code = str(err.get("code") or err.get("type") or "") or None
            msg = err.get("message")
            if msg:
                safe_msg = f"OpenAI error: {msg}"
    except Exception:
        pass

    retry_after: Optional[float] = None
    retry_header = headers.get("retry-after")
    if retry_header:
        try:
            retry_after = float(retry_header)
        except ValueError:
            pass

    if status_code == 401:
        kind = ProviderErrorKind.AUTHENTICATION_ERROR
        retryable = False
    elif status_code == 403:
        kind = ProviderErrorKind.PERMISSION_DENIED
        retryable = False
    elif status_code == 404:
        kind = ProviderErrorKind.NOT_FOUND
        retryable = False
    elif status_code == 429:
        kind = ProviderErrorKind.RATE_LIMIT_EXCEEDED
        retryable = True
    elif status_code in (400, 422):
        lower_msg = safe_msg.lower()
        if "context_length" in lower_msg or "maximum context length" in lower_msg:
            kind = ProviderErrorKind.CONTEXT_LENGTH_EXCEEDED
        elif "content_filter" in lower_msg or "safety" in lower_msg:
            kind = ProviderErrorKind.CONTENT_FILTER
        else:
            kind = ProviderErrorKind.INVALID_REQUEST
        retryable = False
    elif status_code in (500, 502, 503, 504):
        kind = ProviderErrorKind.UPSTREAM_UNAVAILABLE if status_code in (502, 503, 504) else ProviderErrorKind.INTERNAL_SERVER_ERROR
        retryable = True
    else:
        kind = ProviderErrorKind.UNKNOWN
        retryable = (status_code >= 500)

    return ProviderError(
        provider="openai",
        kind=kind,
        status_code=status_code,
        provider_code=provider_code,
        retryable=retryable,
        retry_after_seconds=retry_after,
        safe_message=safe_msg,
    )


class OpenAIProvider(BaseProvider):
    """
    Production-ready asynchronous OpenAI upstream client using pooled HTTPX connections.
    Normalizes upstream errors into typed ProviderError instances without leaking sensitive headers.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.base_url = (base_url or settings.OPENAI_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.UPSTREAM_TIMEOUT_SECONDS

        limits = httpx.Limits(
            max_connections=settings.UPSTREAM_MAX_CONNECTIONS,
            max_keepalive_connections=settings.UPSTREAM_MAX_KEEPALIVE_CONNECTIONS,
        )
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout, connect=5.0),
            limits=limits,
        )

    async def chat_completion(
        self, request: NormalizedInferenceRequest
    ) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError(
                provider="openai",
                kind=ProviderErrorKind.CONFIGURATION_ERROR,
                status_code=500,
                retryable=False,
                safe_message="OpenAI upstream API key is not configured.",
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = request.to_inference_identity_dict()
        if request.stream:
            payload["stream"] = True
        if request.user:
            payload["user"] = request.user

        start_time = time.perf_counter_ns()
        try:
            response = await self._client.post(
                "/chat/completions",
                headers=headers,
                json=payload,
            )
            duration_ms = (time.perf_counter_ns() - start_time) / 1_000_000

            if response.status_code != 200:
                err = _normalize_openai_error(response.status_code, response.headers, response.text)
                logger.error("OpenAI upstream error: status=%d kind=%s msg=%s", response.status_code, err.kind.value, err.safe_message)
                raise err

            data = response.json()
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            return ProviderResponse(
                raw_response=data,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=data.get("model", request.model),
                provider_latency_ms=duration_ms,
            )

        except httpx.TimeoutException as exc:
            duration_ms = (time.perf_counter_ns() - start_time) / 1_000_000
            logger.error("OpenAI upstream timeout after %.2fms", duration_ms)
            raise ProviderError(
                provider="openai",
                kind=ProviderErrorKind.TIMEOUT,
                status_code=504,
                retryable=True,
                safe_message="OpenAI upstream request timed out.",
            ) from exc
        except httpx.RequestError as exc:
            duration_ms = (time.perf_counter_ns() - start_time) / 1_000_000
            logger.error("OpenAI upstream network error: %s", exc)
            raise ProviderError(
                provider="openai",
                kind=ProviderErrorKind.NETWORK_ERROR,
                status_code=502,
                retryable=True,
                safe_message=f"Network error communicating with OpenAI: {type(exc).__name__}",
            ) from exc

    async def chat_completion_stream(
        self, request: NormalizedInferenceRequest
    ) -> AsyncIterator[str]:
        if not self.api_key:
            raise ProviderError(
                provider="openai",
                kind=ProviderErrorKind.CONFIGURATION_ERROR,
                status_code=500,
                retryable=False,
                safe_message="OpenAI upstream API key is not configured.",
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = request.to_inference_identity_dict()
        payload["stream"] = True
        if request.user:
            payload["user"] = request.user

        try:
            req = self._client.build_request(
                "POST",
                "/chat/completions",
                headers=headers,
                json=payload,
            )
            response = await self._client.send(req, stream=True)

            if response.status_code != 200:
                await response.aread()
                err = _normalize_openai_error(response.status_code, response.headers, response.text)
                logger.error("OpenAI upstream stream error: status=%d kind=%s msg=%s", response.status_code, err.kind.value, err.safe_message)
                raise err

            async for line in response.aiter_lines():
                if line:
                    yield f"{line}\n\n"

        except httpx.TimeoutException as exc:
            logger.error("OpenAI upstream stream timeout")
            raise ProviderError(
                provider="openai",
                kind=ProviderErrorKind.TIMEOUT,
                status_code=504,
                retryable=True,
                safe_message="OpenAI upstream stream request timed out.",
            ) from exc
        except httpx.RequestError as exc:
            logger.error("OpenAI upstream stream network error: %s", exc)
            raise ProviderError(
                provider="openai",
                kind=ProviderErrorKind.NETWORK_ERROR,
                status_code=502,
                retryable=True,
                safe_message=f"Network error communicating with OpenAI: {type(exc).__name__}",
            ) from exc

    async def close(self) -> None:
        await self._client.aclose()
