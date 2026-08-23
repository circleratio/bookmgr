import time
from collections import defaultdict

from .errors import RateLimitedError


class LoginRateLimiter:
    """Tracks failed auth attempts per key and blocks further attempts once a threshold is hit."""

    def __init__(self, window_seconds: float = 300, max_attempts: int = 10) -> None:
        self._window_seconds = window_seconds
        self._max_attempts = max_attempts
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        now = time.monotonic()
        recent = [t for t in self._attempts[key] if now - t < self._window_seconds]
        self._attempts[key] = recent
        if len(recent) >= self._max_attempts:
            raise RateLimitedError()

    def record_failure(self, key: str) -> None:
        self._attempts[key].append(time.monotonic())

    def record_success(self, key: str) -> None:
        self._attempts.pop(key, None)
