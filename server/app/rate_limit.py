import threading
import time
from collections import defaultdict

from .errors import RateLimitedError


class LoginRateLimiter:
    """Tracks failed auth attempts per key and blocks further attempts once a threshold is hit.

    Stale entries are pruned whenever a failure is recorded, and the number of
    tracked keys is capped, so failures spread across many client addresses
    cannot grow memory without bound.
    """

    def __init__(
        self, window_seconds: float = 300, max_attempts: int = 10, max_keys: int = 10_000
    ) -> None:
        self._window_seconds = window_seconds
        self._max_attempts = max_attempts
        self._max_keys = max_keys
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
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            if key not in self._attempts and len(self._attempts) >= self._max_keys:
                # Evict the key whose latest failure is oldest to stay under the cap.
                oldest = min(self._attempts, key=lambda k: self._attempts[k][-1])
                del self._attempts[oldest]
            self._attempts[key].append(now)

    def record_success(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def tracked_keys(self) -> int:
        with self._lock:
            return len(self._attempts)

    def _prune(self, now: float) -> None:
        """Drops keys with no failure inside the window. Caller holds the lock."""
        stale = [
            k for k, ts in self._attempts.items()
            if not ts or now - ts[-1] >= self._window_seconds
        ]
        for k in stale:
            del self._attempts[k]
