"""
Single-Flight Request Coalescing (Cache Stampede / Thundering Herd Prevention).

When multiple concurrent requests for the exact same prompt and parameters arrive simultaneously,
only a single in-flight call is dispatched to the upstream provider while concurrent duplicates
await the leader's completion and reuse the resulting response.
"""

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Call:
    """Represents an active in-flight execution."""
    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        # Lock is lazy to support testing across event loops
        self.future: asyncio.Future = (loop or asyncio.get_running_loop()).create_future()
        self.shared_count: int = 0


class RequestCoalescer:
    """
    Single-flight coalescing group.
    Ensures only one execution is active per key at any given time.
    """

    def __init__(self, recent_ttl: float = 2.0) -> None:
        self._calls: Dict[str, Call] = {}
        self._recent_results: Dict[str, Tuple[Any, float]] = {}  # key -> (result, timestamp)
        self._recent_ttl = recent_ttl
        self._lock: Optional[asyncio.Lock] = None

    @property
    def lock(self) -> asyncio.Lock:
        """Lazy lock creation ensures binding to the current event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def do(
        self,
        key: str,
        coroutine_fn: Callable[[], Awaitable[T]],
    ) -> Tuple[T, bool]:
        """
        Executes and returns the result of the given coroutine_fn, making sure
        that only one execution is in-flight for a given key at any given time.

        If a duplicate comes in, the duplicate caller will wait and receive
        the same result.

        Returns:
            (result, is_coalesced_follower) - is_coalesced_follower is True if
            this caller waited on another leader's execution.
        """
        async with self.lock:
            now = time.time()
            # Clean expired recent results
            expired_keys = [k for k, (_, ts) in self._recent_results.items() if now - ts > self._recent_ttl]
            for k in expired_keys:
                del self._recent_results[k]

            if key in self._calls:
                call = self._calls[key]
                call.shared_count += 1
                logger.debug("Coalescing in-flight request for key: %s (waiting count: %d)", key, call.shared_count)
                is_leader = False
            elif key in self._recent_results:
                val, _ = self._recent_results[key]
                logger.debug("Coalescing from recently completed in-flight request for key: %s", key)
                return val, True
            else:
                call = Call(loop=asyncio.get_running_loop())
                self._calls[key] = call
                is_leader = True

        if not is_leader:
            # Wait for leader to finish
            result = await asyncio.shield(call.future)
            return result, True

        # We are the leader: execute the work
        try:
            val = await coroutine_fn()
            async with self.lock:
                self._recent_results[key] = (val, time.time())
            call.future.set_result(val)
            return val, False
        except Exception as exc:
            call.future.set_exception(exc)
            raise
        finally:
            async with self.lock:
                if self._calls.get(key) is call:
                    del self._calls[key]

    def is_in_flight(self, key: str) -> bool:
        """Returns True if a request for this key is currently in-flight."""
        return key in self._calls

    def is_recent(self, key: str) -> bool:
        """Returns True if a request for this key was recently completed within recent_ttl."""
        if key in self._recent_results:
            _, ts = self._recent_results[key]
            if time.time() - ts <= self._recent_ttl:
                return True
        return False

    def in_flight_count(self) -> int:
        """Returns current number of unique in-flight requests."""
        return len(self._calls)

    def clear(self) -> None:
        """Clears all in-flight tracking (useful for test teardown)."""
        self._calls.clear()
        self._recent_results.clear()


_coalescer_instance: Optional[RequestCoalescer] = None


def get_request_coalescer() -> RequestCoalescer:
    """Returns singleton RequestCoalescer instance."""
    global _coalescer_instance
    if _coalescer_instance is None:
        _coalescer_instance = RequestCoalescer()
    return _coalescer_instance


def set_request_coalescer(coalescer: Optional[RequestCoalescer]) -> None:
    """Sets or overrides request coalescer instance."""
    global _coalescer_instance
    _coalescer_instance = coalescer
