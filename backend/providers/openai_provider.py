import json
import logging
import time
from typing import Any, AsyncIterator, Dict, Optional
import httpx
from fastapi import HTTPException, status

from backend.app.config import settings
from backend.normalization.models import NormalizedInferenceRequest
from backend.providers.base import BaseProvider, ProviderResponse

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """
    Production-ready asynchronous OpenAI upstream client using pooled HTTPX connections.
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OpenAI upstream API key is not configured.",
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Build payload
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
                logger.error(
                    "OpenAI upstream error: status=%d body=%s",
                    response.status_code,
                    response.text,
                )
                try:
                    err_json = response.json()
                    err_msg = err_json.get("error", {}).get("message", response.text)
                except Exception:
                    err_msg = response.text

                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Upstream provider error: {err_msg}",
                )

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
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Upstream LLM provider request timed out.",
            ) from exc
        except httpx.RequestError as exc:
            duration_ms = (time.perf_counter_ns() - start_time) / 1_000_000
            logger.error("OpenAI upstream network error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Network error communicating with upstream provider: {str(exc)}",
            ) from exc

    async def chat_completion_stream(
        self, request: NormalizedInferenceRequest
    ) -> AsyncIterator[str]:
        if not self.api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OpenAI upstream API key is not configured.",
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
                logger.error(
                    "OpenAI upstream stream error: status=%d body=%s",
                    response.status_code,
                    response.text,
                )
                try:
                    err_json = response.json()
                    err_msg = err_json.get("error", {}).get("message", response.text)
                except Exception:
                    err_msg = response.text

                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Upstream provider error: {err_msg}",
                )

            async for line in response.aiter_lines():
                if line:
                    yield f"{line}\n\n"

        except httpx.TimeoutException as exc:
            logger.error("OpenAI upstream stream timeout")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Upstream LLM provider request timed out.",
            ) from exc
        except httpx.RequestError as exc:
            logger.error("OpenAI upstream stream network error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Network error communicating with upstream provider: {str(exc)}",
            ) from exc

    async def close(self) -> None:
        await self._client.aclose()
