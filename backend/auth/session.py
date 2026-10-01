from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Optional
from fastapi import Response

from backend.app.config import settings


def generate_session_token() -> str:
    """Generates a high-entropy URL-safe session token (256 bits)."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Hashes a raw session token with SHA-256 for secure database storage."""
    if not token:
        raise ValueError("Session token cannot be empty")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def calculate_session_expiry() -> datetime:
    """Calculates the absolute expiration timestamp for a new or refreshed session."""
    return datetime.now(timezone.utc) + timedelta(seconds=settings.SESSION_COOKIE_MAX_AGE)


def is_session_expired(expires_at: datetime) -> bool:
    """Safely checks if a session expiration datetime has passed, handling timezone awareness."""
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < datetime.now(timezone.utc)


def set_session_cookie(
    response: Response,
    session_token: str,
    max_age: Optional[int] = None,
) -> None:
    """
    Sets the secure HTTP-only session cookie on the response.
    """
    cookie_max_age = max_age if max_age is not None else settings.SESSION_COOKIE_MAX_AGE
    secure = settings.SESSION_COOKIE_SECURE
    if secure is None:
        secure = settings.ENVIRONMENT == "production"

    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_token,
        max_age=cookie_max_age,
        expires=cookie_max_age,
        path="/",
        domain=None,
        secure=secure,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )


def delete_session_cookie(response: Response) -> None:
    """
    Deletes the session cookie by setting an expired cookie header.
    """
    secure = settings.SESSION_COOKIE_SECURE
    if secure is None:
        secure = settings.ENVIRONMENT == "production"

    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        domain=None,
        secure=secure,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )
