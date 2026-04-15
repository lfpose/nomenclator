from collections import deque
from time import time


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = time()
        bucket = self._hits.setdefault(key, deque())
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        return True


AUTH_LIMITER = RateLimiter(limit=5, window_seconds=60.0)
COMMIT_LIMITER = RateLimiter(limit=10, window_seconds=3600.0)
GENERAL_LIMITER = RateLimiter(limit=60, window_seconds=60.0)
REVIEW_LIMITER = RateLimiter(limit=10, window_seconds=60.0)
