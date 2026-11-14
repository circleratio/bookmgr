import pytest

from app import rate_limit
from app.errors import RateLimitedError
from app.rate_limit import LoginRateLimiter


def test_blocks_after_max_attempts():
    limiter = LoginRateLimiter(max_attempts=3)
    for _ in range(3):
        limiter.check("a")
        limiter.record_failure("a")
    with pytest.raises(RateLimitedError):
        limiter.check("a")


def test_stale_keys_pruned_on_failure(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now[0])
    limiter = LoginRateLimiter(window_seconds=300)
    for i in range(100):
        limiter.record_failure(f"ip{i}")
    assert limiter.tracked_keys() == 100

    now[0] += 301
    limiter.record_failure("new")
    assert limiter.tracked_keys() == 1


def test_key_count_is_capped(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now[0])
    limiter = LoginRateLimiter(max_keys=5)
    for i in range(20):
        now[0] += 1
        limiter.record_failure(f"ip{i}")
    assert limiter.tracked_keys() == 5
    # The most recent offender is still tracked and still limited.
    for _ in range(9):
        limiter.record_failure("ip19")
    with pytest.raises(RateLimitedError):
        limiter.check("ip19")
