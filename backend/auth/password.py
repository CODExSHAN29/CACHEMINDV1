import logging
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

logger = logging.getLogger(__name__)

# Argon2id hasher configured with OWASP recommendations (memory-hard, resistant to GPU attacks)
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def normalize_email(email: str) -> str:
    """Canonicalizes an email address to lowercase and stripped of surrounding whitespace."""
    if not email:
        return ""
    return email.strip().lower()


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2id."""
    if not password:
        raise ValueError("Password cannot be empty")
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verifies a plaintext password against an Argon2id password hash using constant-time comparison.
    Returns True if valid, False otherwise.
    """
    if not password or not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception as exc:
        logger.warning("Unexpected error during password verification: %s", exc)
        return False


def needs_rehash(password_hash: str) -> bool:
    """Checks if the stored password hash needs to be updated to match current Argon2id parameters."""
    if not password_hash:
        return False
    try:
        return _hasher.check_needs_rehash(password_hash)
    except Exception:
        return False
