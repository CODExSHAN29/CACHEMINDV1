from dataclasses import dataclass
from typing import Dict


@dataclass
class RateLimitResult:
    """Encapsulates the verdict and state of a rate limit evaluation."""
    allowed: bool
    remaining_requests: int
    limit_requests: int
    remaining_tokens: int
    limit_tokens: int
    reset_seconds: int
    retry_after: int = 0

    def to_headers(self) -> Dict[str, str]:
        """Returns standard HTTP rate-limiting headers."""
        headers = {
            "X-RateLimit-Limit-Requests": str(self.limit_requests),
            "X-RateLimit-Remaining-Requests": str(max(0, self.remaining_requests)),
            "X-RateLimit-Limit-Tokens": str(self.limit_tokens),
            "X-RateLimit-Remaining-Tokens": str(max(0, self.remaining_tokens)),
            "X-RateLimit-Reset-Requests": str(self.reset_seconds),
        }
        if not self.allowed and self.retry_after > 0:
            headers["Retry-After"] = str(self.retry_after)
        return headers
