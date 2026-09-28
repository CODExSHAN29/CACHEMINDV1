class CacheMindError(Exception):
    """Base exception for all CacheMind SDK errors."""
    pass


class AuthenticationError(CacheMindError):
    """Raised when API key is invalid or unauthorized."""
    pass


class RateLimitError(CacheMindError):
    """Raised when rate limit is exceeded."""
    pass


class GatewayError(CacheMindError):
    """Raised when the CacheMind Gateway returns a 5xx or connection error."""
    pass
