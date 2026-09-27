import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional


def format_sse_chunk(
    request_id: str,
    model: str,
    content: Optional[str] = None,
    role: Optional[str] = None,
    finish_reason: Optional[str] = None,
    system_fingerprint: Optional[str] = None,
    usage: Optional[Dict[str, Any]] = None,
    created: Optional[int] = None,
) -> str:
    """
    Formats a single OpenAI-compliant Server-Sent Events (SSE) data chunk line.
    Example:
    data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":12345,"model":"gpt-4o",...}\n\n
    """
    delta: Dict[str, Any] = {}
    if role is not None:
        delta["role"] = role
    if content is not None:
        delta["content"] = content

    chunk: Dict[str, Any] = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created if created is not None else int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "logprobs": None,
                "finish_reason": finish_reason,
            }
        ],
    }

    if system_fingerprint is not None:
        chunk["system_fingerprint"] = system_fingerprint

    if usage is not None:
        chunk["usage"] = usage

    return f"data: {json.dumps(chunk, separators=(',', ':'))}\n\n"


def format_sse_done() -> str:
    """
    Returns the final SSE stream termination marker.
    """
    return "data: [DONE]\n\n"


async def create_cached_stream_generator(
    cached_payload: Dict[str, Any],
    request_id: str,
    model: str,
    chunk_size: int = 16,
) -> AsyncIterator[str]:
    """
    Generates OpenAI-compliant SSE chunks from a cached complete response payload.
    Emits an initial role chunk, token/word chunks, a finish_reason chunk, and data: [DONE].
    """
    created = cached_payload.get("created", int(time.time()))
    system_fingerprint = cached_payload.get("system_fingerprint", None)
    choices = cached_payload.get("choices", [])

    if not choices:
        yield format_sse_done()
        return

    choice = choices[0]
    message = choice.get("message", {})
    role = message.get("role", "assistant")
    content = message.get("content", "")

    # 1. Initial role chunk
    yield format_sse_chunk(
        request_id=request_id,
        model=model,
        role=role,
        content=None,
        finish_reason=None,
        system_fingerprint=system_fingerprint,
        created=created,
    )

    # 2. Content chunks
    if content:
        # Split content into natural word chunks or character slices
        words = content.split(" ")
        current_chunk = []
        current_len = 0

        for i, word in enumerate(words):
            current_chunk.append(word)
            current_len += len(word) + 1
            # Emit when chunk size threshold is met or last word
            if current_len >= chunk_size or i == len(words) - 1:
                token_text = " ".join(current_chunk)
                # Add trailing space if not the last word in text
                if i < len(words) - 1:
                    token_text += " "

                yield format_sse_chunk(
                    request_id=request_id,
                    model=model,
                    content=token_text,
                    finish_reason=None,
                    system_fingerprint=system_fingerprint,
                    created=created,
                )
                current_chunk = []
                current_len = 0

    # 3. Finish chunk
    finish_reason = choice.get("finish_reason", "stop")
    usage = cached_payload.get("usage", None)
    yield format_sse_chunk(
        request_id=request_id,
        model=model,
        content=None,
        finish_reason=finish_reason,
        system_fingerprint=system_fingerprint,
        usage=usage,
        created=created,
    )

    # 4. Done marker
    yield format_sse_done()
