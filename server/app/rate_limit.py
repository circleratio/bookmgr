import threading
import time
from collections import defaultdict

from .errors import RateLimitedError


class LoginRateLimiter:
    """Tracks failed auth attempts per key and blocks further attempts once a threshold is hit."""

    def __init__(self, window_seconds: float = 300, max_attempts: int = 10) -> None:
        self._window_seconds = window_seconds
        self._max_attempts = max_attempts
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            if key not in self._attempts:
                return
            recent = [t for t in self._attempts[key] if now - t < self._window_seconds]
            if recent:
                self._attempts[key] = recent
            else:
                del self._attempts[key]
        if len(recent) >= self._max_attempts:
            raise RateLimitedError()

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._attempts[key].append(time.monotonic())

    def record_success(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)
