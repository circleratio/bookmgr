import pytest

from app import auth
from app.auth import SESSION_IDLE_SECONDS, SESSION_TTL_SECONDS, SessionStore

DAY = 24 * 60 * 60


@pytest.fixture
def now(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: clock[0])
    return clock


def test_new_session_is_valid(now):
    store = SessionStore()
    assert store.is_valid(store.create())


def test_unknown_or_missing_token_is_invalid(now):
    store = SessionStore()
    assert not store.is_valid("nope")
    assert not store.is_valid(None)
    assert not store.is_valid("")


def test_idle_session_expires(now):
    store = SessionStore()
    token = store.create()
    now[0] += SESSION_IDLE_SECONDS + 1
    assert not store.is_valid(token)


def test_use_restarts_idle_timer(now):
    store = SessionStore()
    token = store.create()
    for _ in range(3):
        now[0] += SESSION_IDLE_SECONDS - DAY
        assert store.is_valid(token)


def test_absolute_lifetime_applies_despite_regular_use(now):
    store = SessionStore()
    token = store.create()
    elapsed = 0
    while elapsed + DAY <= SESSION_TTL_SECONDS:
        now[0] += DAY
        elapsed += DAY
        assert store.is_valid(token)
    now[0] += DAY
    assert not store.is_valid(token)


def test_expired_session_stays_invalid_after_check(now):
    store = SessionStore()
    token = store.create()
    now[0] += SESSION_IDLE_SECONDS + 1
    assert not store.is_valid(token)
    now[0] -= SESSION_IDLE_SECONDS  # even if the clock reading were earlier
    assert not store.is_valid(token)


def test_revoke(now):
    store = SessionStore()
    token = store.create()
    store.revoke(token)
    assert not store.is_valid(token)


def test_idle_sessions_pruned_on_create(now):
    store = SessionStore()
    stale = [store.create() for _ in range(10)]
    now[0] += SESSION_IDLE_SECONDS + 1
    store.create()
    assert len(store._sessions) == 1
    assert not any(store.is_valid(t) for t in stale)
