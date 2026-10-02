import asyncio
import hashlib
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from backend.normalization.canonicalizer import canonicalize_request
from backend.normalization.models import NormalizedInferenceRequest
from backend.providers.base import BaseProvider, ProviderResponse
from backend.streaming.sse import format_sse_chunk, format_sse_done


class MockProvider(BaseProvider):
    """
    Deterministic, first-class test double for upstream LLM providers.
    Tracks exact call counts and supports latency, failure simulation, and multi-provider tagging.
    """

    def __init__(
        self,
        provider_name: str = "mock",
        simulated_latency_ms: float = 0.0,
        error_mode: Optional[str] = None,
        custom_response_text: Optional[str] = None,
        fail_next_n_calls: int = 0,
    ) -> None:
        self.provider_name = provider_name
        self.call_count: int = 0
        self.simulated_latency_ms = simulated_latency_ms
        self.error_mode = error_mode  # e.g., "rate_limit_429", "server_error_500", "timeout"
        self.custom_response_text = custom_response_text
        self.fail_next_n_calls = fail_next_n_calls
        self.history: List[NormalizedInferenceRequest] = []

    def reset(self) -> None:
        """Resets call counts and recorded history."""
        self.call_count = 0
        self.history.clear()
        self.error_mode = None
        self.fail_next_n_calls = 0

    def _check_and_trigger_error(self) -> None:
        if self.fail_next_n_calls > 0:
            self.fail_next_n_calls -= 1
            mode = self.error_mode or "server_error_500"
            if mode == "rate_limit_429":
                raise RuntimeError("Upstream rate limit exceeded (429)")
            elif mode == "timeout":
                raise asyncio.TimeoutError("Upstream connection timed out")
            else:
                raise RuntimeError("Upstream internal server error (500)")

        if self.error_mode == "rate_limit_429":
            raise RuntimeError("Upstream rate limit exceeded (429)")
        elif self.error_mode == "server_error_500":
            raise RuntimeError("Upstream internal server error (500)")
        elif self.error_mode == "timeout":
            raise asyncio.TimeoutError("Upstream connection timed out")

    async def chat_completion(
        self, request: NormalizedInferenceRequest
    ) -> ProviderResponse:
        self.call_count += 1
        self.history.append(request)

        start_time = time.perf_counter_ns()

        if self.simulated_latency_ms > 0:
            await asyncio.sleep(self.simulated_latency_ms / 1000.0)

        self._check_and_trigger_error()

        # Synthesize deterministic response based on input hash
        req_hash = hashlib.sha256(canonicalize_request(request).encode("utf-8")).hexdigest()[:12]

        last_user_msg = "Hello"
        for m in reversed(request.messages):
            if m.role == "user":
                if isinstance(m.content, str):
                    last_user_msg = m.content
                    break
                elif isinstance(m.content, list):
                    text_parts = [
                        p["text"]
                        for p in m.content
                        if isinstance(p, dict) and p.get("type") == "text" and isinstance(p.get("text"), str)
                    ]
                    if text_parts:
                        last_user_msg = " ".join(text_parts)
                        break

        reply_content = (
            self.custom_response_text
            if self.custom_response_text is not None
            else f"Mock response for: '{last_user_msg}' [hash:{req_hash}]"
        )

        prompt_tokens = sum(
            len(str(m.content or "")) // 4 + 4 for m in request.messages
        )
        completion_tokens = max(1, len(reply_content) // 4)

        raw_response: Dict[str, Any] = {
            "id": f"mock-cmpl-{req_hash}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": reply_content,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "system_fingerprint": f"fp_mock_{req_hash[:8]}",
        }

        duration_ms = (time.perf_counter_ns() - start_time) / 1_000_000

        return ProviderResponse(
            raw_response=raw_response,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            model=request.model,
            provider_latency_ms=duration_ms,
        )

    async def chat_completion_stream(
        self, request: NormalizedInferenceRequest
    ) -> AsyncIterator[str]:
        self.call_count += 1
        self.history.append(request)

        if self.simulated_latency_ms > 0:
            await asyncio.sleep(self.simulated_latency_ms / 1000.0)

        self._check_and_trigger_error()

        req_hash = hashlib.sha256(canonicalize_request(request).encode("utf-8")).hexdigest()[:12]
        request_id = f"mock-cmpl-{req_hash}"
        created = int(time.time())
        system_fingerprint = f"fp_mock_{req_hash[:8]}"

        last_user_msg = "Hello"
        for m in reversed(request.messages):
            if m.role == "user":
                if isinstance(m.content, str):
                    last_user_msg = m.content
                    break
                elif isinstance(m.content, list):
                    text_parts = [
                        p["text"]
                        for p in m.content
                        if isinstance(p, dict) and p.get("type") == "text" and isinstance(p.get("text"), str)
                    ]
                    if text_parts:
                        last_user_msg = " ".join(text_parts)
                        break

        reply_content = (
            self.custom_response_text
            if self.custom_response_text is not None
            else f"Mock response for: '{last_user_msg}' [hash:{req_hash}]"
        )

        prompt_tokens = sum(
            len(str(m.content or "")) // 4 + 4 for m in request.messages
        )
        completion_tokens = max(1, len(reply_content) // 4)

        # 1. Initial role chunk
        yield format_sse_chunk(
            request_id=request_id,
            model=request.model,
            role="assistant",
            content=None,
            system_fingerprint=system_fingerprint,
            created=created,
        )

        # 2. Content chunks
        words = reply_content.split(" ")
        for i, word in enumerate(words):
            token_text = word if i == len(words) - 1 else word + " "
            yield format_sse_chunk(
                request_id=request_id,
                model=request.model,
                content=token_text,
                system_fingerprint=system_fingerprint,
                created=created,
            )

        # 3. Finish reason & usage chunk
        yield format_sse_chunk(
            request_id=request_id,
            model=request.model,
            finish_reason="stop",
            system_fingerprint=system_fingerprint,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            created=created,
        )

        # 4. Done marker
        yield format_sse_done()

    async def close(self) -> None:
        pass
