import time
from typing import Any, Dict, List, Optional, Union
import httpx

from .exceptions import AuthenticationError, CacheMindError, GatewayError, RateLimitError
from .models import (
    CacheTelemetry,
    ChatCompletionChoice,
    ChatCompletionResponse,
    ChatMessage,
    PurgeResult,
    UsageInfo,
    WarmResult,
)


class AsyncChatCompletions:
    def __init__(self, client: "AsyncCacheMindClient"):
        self._client = client

    async def create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tags: Optional[List[str]] = None,
        namespace: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> ChatCompletionResponse:
        headers = dict(self._client._base_headers)
        if tags:
            headers["X-CacheMind-Tags"] = ",".join(tags)
        if namespace:
            headers["X-CacheMind-Namespace"] = namespace
        if extra_headers:
            headers.update(extra_headers)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        start_time = time.perf_counter()
        try:
            resp = await self._client._http_client.post(
                f"{self._client.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=self._client.timeout,
            )
        except httpx.RequestError as exc:
            raise GatewayError(f"Failed to reach CacheMind Gateway: {exc}") from exc

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if resp.status_code == 401 or resp.status_code == 403:
            raise AuthenticationError(f"Unauthorized: {resp.text}")
        if resp.status_code == 429:
            raise RateLimitError(f"Rate limit exceeded: {resp.text}")
        if resp.status_code >= 500:
            raise GatewayError(f"Gateway internal error ({resp.status_code}): {resp.text}")
        if resp.status_code >= 400:
            raise CacheMindError(f"Request error ({resp.status_code}): {resp.text}")

        data = resp.json()

        # Parse CacheMind Telemetry from response headers
        cache_status = resp.headers.get("x-cachemind-cache", "CACHE_MISS")
        tokens_saved = int(resp.headers.get("x-cachemind-tokens-saved", "0"))
        cost_saved = float(resp.headers.get("x-cachemind-cost-saved", "0.0"))
        similarity = resp.headers.get("x-cachemind-similarity")
        sim_score = float(similarity) if similarity else None

        telemetry = CacheTelemetry(
            status=cache_status,  # type: ignore
            similarity_score=sim_score,
            tokens_saved=tokens_saved,
            cost_saved_usd=cost_saved,
            latency_ms=round(elapsed_ms, 2),
        )

        choices = [
            ChatCompletionChoice(
                index=c.get("index", 0),
                message=ChatMessage(
                    role=c["message"]["role"],
                    content=c["message"]["content"],
                ),
                finish_reason=c.get("finish_reason"),
            )
            for c in data.get("choices", [])
        ]

        usage = None
        if "usage" in data:
            usage = UsageInfo(**data["usage"])

        return ChatCompletionResponse(
            id=data.get("id", ""),
            created=data.get("created", int(time.time())),
            model=data.get("model", model),
            choices=choices,
            usage=usage,
            cachemind=telemetry,
        )


class AsyncCacheManagement:
    def __init__(self, client: "AsyncCacheMindClient"):
        self._client = client

    async def purge(
        self,
        tenant_id: str,
        project_id: Optional[str] = None,
        model: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> PurgeResult:
        resp = await self._client._http_client.post(
            f"{self._client.base_url}/v1/cache/purge",
            json={
                "tenant_id": tenant_id,
                "project_id": project_id,
                "model": model,
                "tags": tags,
            },
            headers=self._client._base_headers,
            timeout=self._client.timeout,
        )
        if not resp.is_success:
            raise CacheMindError(f"Purge failed: {resp.text}")
        data = resp.json()
        return PurgeResult(**data)

    async def warm(
        self,
        tenant_id: str,
        project_id: str,
        items: List[Dict[str, str]],
    ) -> WarmResult:
        resp = await self._client._http_client.post(
            f"{self._client.base_url}/v1/cache/warm",
            json={
                "tenant_id": tenant_id,
                "project_id": project_id,
                "items": items,
            },
            headers=self._client._base_headers,
            timeout=self._client.timeout,
        )
        if not resp.is_success:
            raise CacheMindError(f"Warm failed: {resp.text}")
        data = resp.json()
        return WarmResult(**data)


class AsyncChat:
    def __init__(self, client: "AsyncCacheMindClient"):
        self.completions = AsyncChatCompletions(client)


class AsyncCacheMindClient:
    """Official Asynchronous CacheMind Python SDK Client."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._base_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "CacheMind-Python-SDK/0.1.0",
        }
        self._http_client = httpx.AsyncClient(timeout=self.timeout)
        self.chat = AsyncChat(self)
        self.cache = AsyncCacheManagement(self)

    async def close(self) -> None:
        await self._http_client.aclose()

    async def __aenter__(self) -> "AsyncCacheMindClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
