"""Sliding-window rate limiter used to throttle brute-force login attempts.

In-memory implementation: suitable for a single process. For a multi-instance deployment,
provide another implementation of :class:`RateLimiter` backed by Redis.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Protocol


class RateLimiter(Protocol):
    def hit(self, key: str) -> int | None:
        """Record an attempt. Returns ``None`` if allowed, else seconds to wait."""
        ...

    def reset(self, key: str) -> None: ...


class InMemoryRateLimiter:
    def __init__(
        self, max_attempts: int, window_seconds: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> int | None:
        now = self._clock()
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            while bucket and now - bucket[0] >= self._window:
                bucket.popleft()
            if len(bucket) >= self._max:
                return max(1, int(self._window - (now - bucket[0])))
            bucket.append(now)
            return None

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)
