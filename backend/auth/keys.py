import hashlib
import hmac
import secrets
from typing import Tuple


def hash_api_key(raw_key: str) -> str:
    """Computes a SHA-256 hash of the raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def verify_api_key(raw_key: str, key_hash: str) -> bool:
    """Verifies a raw API key against a stored SHA-256 hash using constant-time comparison."""
    computed_hash = hash_api_key(raw_key)
    return hmac.compare_digest(computed_hash, key_hash)


def generate_api_key(prefix: str = "cm_live_") -> Tuple[str, str, str]:
    """
    Generates a secure API key with 192 bits of cryptographic entropy.
    Returns:
        (raw_key, key_prefix, key_hash)
    """
    # 24 bytes = 48 hex characters = 192 bits entropy
    secret = secrets.token_hex(24)
    raw_key = f"{prefix}{secret}"
    key_prefix = raw_key[:16]
    key_hash = hash_api_key(raw_key)
    return raw_key, key_prefix, key_hash
