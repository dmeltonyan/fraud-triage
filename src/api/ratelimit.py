"""A small in-memory rate limiter: at most `max_requests` per key (an IP address) in
any `window_seconds`. Kept in the server's memory, so it resets when the server
restarts and isn't shared between several server copies; enough for a demo."""

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float = 60.0, clock=time.monotonic):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clock = clock  # replaceable in tests
        self.recent: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """Record a request from `key` and say whether it is within the limit."""
        now = self.clock()
        times = self.recent[key]
        while times and now - times[0] >= self.window_seconds:
            times.popleft()  # forget requests older than the window
        if len(times) >= self.max_requests:
            return False
        times.append(now)
        return True
