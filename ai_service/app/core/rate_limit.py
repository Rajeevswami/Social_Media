"""Sliding-window rate limiter keyed on the caller's API key.

In-process on purpose: one worker per instance is enough to protect the model
provider bill, and it needs no Redis. For multi-instance deployments swap the
store for Redis (same interface) — see `SlidingWindowLimiter.record`.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> tuple[bool, int, int]:
        """Return (allowed, remaining, retry_after_seconds)."""
        now = time.monotonic()
        async with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] >= self.window_seconds:
                bucket.popleft()

            if len(bucket) >= self.max_requests:
                retry_after = max(1, int(self.window_seconds - (now - bucket[0])) + 1)
                return False, 0, retry_after

            bucket.append(now)
            return True, self.max_requests - len(bucket), 0

    async def reset(self, key: str | None = None) -> None:
        async with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)
