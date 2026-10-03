import httpx
import pytest

from backend.providers.anthropic_provider import _normalize_anthropic_error
from backend.providers.base import ProviderError, ProviderErrorKind
from backend.providers.ollama_provider import _normalize_ollama_error
from backend.providers.openai_provider import _normalize_openai_error


def test_openai_error_normalization():
    # 401 Authentication
    headers = httpx.Headers({"content-type": "application/json"})
    body_401 = '{"error": {"message": "Invalid API key provided", "type": "invalid_request_error", "code": "invalid_api_key"}}'
    err = _normalize_openai_error(401, headers, body_401)
    assert err.provider == "openai"
    assert err.kind == ProviderErrorKind.AUTHENTICATION_ERROR
    assert err.status_code == 401
    assert err.retryable is False
    assert err.provider_code == "invalid_api_key"
    assert "Invalid API key" in err.safe_message

    # 429 Rate Limit with Retry-After
    headers_429 = httpx.Headers({"retry-after": "5.5"})
    body_429 = '{"error": {"message": "Rate limit reached for requests", "type": "requests", "code": "rate_limit_exceeded"}}'
    err_429 = _normalize_openai_error(429, headers_429, body_429)
    assert err_429.kind == ProviderErrorKind.RATE_LIMIT_EXCEEDED
    assert err_429.retryable is True
    assert err_429.retry_after_seconds == 5.5

    # 400 Context Length Exceeded
    body_ctx = '{"error": {"message": "This model\'s maximum context length is 8192 tokens. However, your messages resulted in 10000 tokens.", "type": "invalid_request_error"}}'
    err_ctx = _normalize_openai_error(400, headers, body_ctx)
    assert err_ctx.kind == ProviderErrorKind.CONTEXT_LENGTH_EXCEEDED
    assert err_ctx.retryable is False

    # 503 Upstream Unavailable
    err_503 = _normalize_openai_error(503, headers, "<html>Bad Gateway</html>")
    assert err_503.kind == ProviderErrorKind.UPSTREAM_UNAVAILABLE
    assert err_503.retryable is True


def test_anthropic_error_normalization():
    # 401 Authentication
    headers = httpx.Headers({"content-type": "application/json"})
    body_401 = '{"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}'
    err_401 = _normalize_anthropic_error(401, headers, body_401)
    assert err_401.provider == "anthropic"
    assert err_401.kind == ProviderErrorKind.AUTHENTICATION_ERROR
    assert err_401.provider_code == "authentication_error"
    assert err_401.retryable is False
    assert "invalid x-api-key" in err_401.safe_message

    # 429 Rate Limit with Retry-After
    headers_429 = httpx.Headers({"retry-after": "12.0"})
    body_429 = '{"type": "error", "error": {"type": "rate_limit_error", "message": "Number of request tokens has exceeded your per-minute rate limit"}}'
    err_429 = _normalize_anthropic_error(429, headers_429, body_429)
    assert err_429.kind == ProviderErrorKind.RATE_LIMIT_EXCEEDED
    assert err_429.retryable is True
    assert err_429.retry_after_seconds == 12.0

    # 529 Overloaded (Anthropic-specific status code)
    body_529 = '{"type": "error", "error": {"type": "overloaded_error", "message": "Anthropic is currently overloaded"}}'
    err_529 = _normalize_anthropic_error(529, headers, body_529)
    assert err_529.kind == ProviderErrorKind.UPSTREAM_UNAVAILABLE
    assert err_529.retryable is True


def test_ollama_error_normalization():
    # 404 Model Not Found
    body_404 = '{"error": "model \'unknown_model\' not found, try pulling it first"}'
    err_404 = _normalize_ollama_error(404, body_404)
    assert err_404.provider == "ollama"
    assert err_404.kind == ProviderErrorKind.NOT_FOUND
    assert err_404.retryable is False

    # 500 Internal Error
    body_500 = '{"error": "cuda out of memory"}'
    err_500 = _normalize_ollama_error(500, body_500)
    assert err_500.kind == ProviderErrorKind.INTERNAL_SERVER_ERROR
    assert err_500.retryable is True
