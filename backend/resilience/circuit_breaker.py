import asyncio
from enum import Enum
import logging
import time
from typing import Dict, Optional

from backend.app.config import settings

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"        # Normal operational state
    OPEN = "OPEN"            # Tripped; fails fast to protect downstream/upstream
    HALF_OPEN = "HALF_OPEN"  # Testing upstream recovery with limited probes


class CircuitBreaker:
    """
    High-performance, async-safe Circuit Breaker implementing the
    CLOSED -> OPEN -> HALF_OPEN state machine.
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: Optional[int] = None,
        recovery_timeout_seconds: Optional[float] = None,
        half_open_success_threshold: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = (
            failure_threshold
            if failure_threshold is not None
            else settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        )
        self.recovery_timeout_seconds = (
            recovery_timeout_seconds
            if recovery_timeout_seconds is not None
            else settings.CIRCUIT_BREAKER_RECOVERY_SECONDS
        )
        self.half_open_success_threshold = half_open_success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count: int = 0
        self._consecutive_successes: int = 0
        self._opened_at: Optional[float] = None
        self._last_state_change: float = time.time()
        self._lock: Optional[asyncio.Lock] = None

    @property
    def lock(self) -> asyncio.Lock:
        """Lazy lock creation ensures binding to the current event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    async def can_execute(self) -> bool:
        """
        Determines whether a request should be dispatched to the target upstream.
        Transitions from OPEN to HALF_OPEN when recovery cooldown expires.
        """
        async with self.lock:
            if self._state == CircuitState.CLOSED:
                return True

            now = time.time()
            if self._state == CircuitState.OPEN:
                if self._opened_at and (now - self._opened_at >= self.recovery_timeout_seconds):
                    logger.info(
                        "Circuit breaker '%s' recovery timeout expired (%.2fs). Entering HALF_OPEN probe mode.",
                        self.name,
                        now - self._opened_at,
                    )
                    self._state = CircuitState.HALF_OPEN
                    self._consecutive_successes = 0
                    self._last_state_change = now
                    return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                # Permit probe execution in HALF_OPEN state
                return True

            return False

    async def record_success(self) -> None:
        """
        Records a successful upstream call.
        If in HALF_OPEN mode, transitions back to CLOSED once threshold met.
        """
        async with self.lock:
            now = time.time()
            if self._state == CircuitState.HALF_OPEN:
                self._consecutive_successes += 1
                if self._consecutive_successes >= self.half_open_success_threshold:
                    logger.info(
                        "Circuit breaker '%s' probe successful (%d/%d). Transitioning to CLOSED.",
                        self.name,
                        self._consecutive_successes,
                        self.half_open_success_threshold,
                    )
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._opened_at = None
                    self._last_state_change = now
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def record_failure(self) -> None:
        """
        Records an upstream error (429, 5xx, timeout).
        Trips CLOSED -> OPEN if threshold is reached, or HALF_OPEN -> OPEN immediately.
        """
        async with self.lock:
            now = time.time()
            self._failure_count += 1
            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    "Circuit breaker '%s' probe failed in HALF_OPEN state. Tripping to OPEN.",
                    self.name,
                )
                self._state = CircuitState.OPEN
                self._opened_at = now
                self._last_state_change = now
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    logger.warning(
                        "Circuit breaker '%s' reached failure threshold (%d/%d). Tripping to OPEN.",
                        self.name,
                        self._failure_count,
                        self.failure_threshold,
                    )
                    self._state = CircuitState.OPEN
                    self._opened_at = now
                    self._last_state_change = now

    async def reset(self) -> None:
        """Force reset to CLOSED state."""
        async with self.lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._consecutive_successes = 0
            self._opened_at = None
            self._last_state_change = time.time()


class CircuitBreakerRegistry:
    """
    Registry for managing CircuitBreaker instances across providers and models.
    """

    def __init__(self) -> None:
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock: Optional[asyncio.Lock] = None

    @property
    def lock(self) -> asyncio.Lock:
        """Lazy lock creation ensures binding to the current event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def get_breaker(
        self,
        name: str,
        failure_threshold: Optional[int] = None,
        recovery_timeout_seconds: Optional[float] = None,
    ) -> CircuitBreaker:
        name_clean = name.lower()
        if name_clean not in self._breakers:
            self._breakers[name_clean] = CircuitBreaker(
                name=name_clean,
                failure_threshold=failure_threshold,
                recovery_timeout_seconds=recovery_timeout_seconds,
            )
        return self._breakers[name_clean]

    def reset_all(self) -> None:
        for breaker in self._breakers.values():
            breaker._state = CircuitState.CLOSED
            breaker._failure_count = 0
            breaker._consecutive_successes = 0
            breaker._opened_at = None


_breaker_registry_instance: Optional[CircuitBreakerRegistry] = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    global _breaker_registry_instance
    if _breaker_registry_instance is None:
        _breaker_registry_instance = CircuitBreakerRegistry()
    return _breaker_registry_instance
