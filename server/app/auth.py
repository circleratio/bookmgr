import ipaddress
import secrets
import threading
import time
from urllib.parse import urlsplit

from fastapi import Header, Request

from .errors import ForbiddenError, UnauthorizedError

SESSION_COOKIE_NAME = "session"
# Absolute lifetime from login, also used as the cookie's Max-Age.
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
# A session unused for this long expires before reaching its absolute lifetime.
SESSION_IDLE_SECONDS = 7 * 24 * 60 * 60  # 7 days


def client_key(request: Request) -> str:
    """Identifies the client for rate limiting.

    IPv6 clients are grouped by their /64 prefix, since a single host is
    typically allocated a whole /64 and could otherwise rotate addresses to
    evade the limit.
    """
    host = request.client.host if request.client else "unknown"
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return host
    if addr.version == 6:
        return str(ipaddress.ip_network(f"{addr}/64", strict=False))
    return host


def verify_api_key(candidate: str | None, request: Request) -> bool:
    if candidate is None:
        return False
    # Compare as bytes: compare_digest raises TypeError on non-ASCII str,
    # which would turn a wrong key into a 500 and skip the failure count.
    return secrets.compare_digest(
        candidate.encode("utf-8"), request.app.state.api_key.encode("utf-8")
    )


class SessionStore:
    """In-memory session tokens, safe for concurrent access from FastAPI's
    thread pool.

    A session expires SESSION_TTL_SECONDS after login, or earlier once it has
    gone unused for SESSION_IDLE_SECONDS. Each successful validation counts
    as use and restarts the idle timer.
    """

    def __init__(self) -> None:
        # token -> (absolute expiry, last use), both on the monotonic clock.
        self._sessions: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _is_live(expires_at: float, last_used: float, now: float) -> bool:
        return now <= expires_at and now - last_used <= SESSION_IDLE_SECONDS

    def create(self) -> str:
        """Issue a random session token, independent of the API key itself."""
        token = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self._lock:
            # Prune expired sessions so the store does not grow without bound.
            for t in [t for t, s in self._sessions.items() if not self._is_live(*s, now)]:
                del self._sessions[t]
            self._sessions[token] = (now + SESSION_TTL_SECONDS, now)
        return token

    def revoke(self, token: str | None) -> None:
        if token:
            with self._lock:
                self._sessions.pop(token, None)

    def is_valid(self, token: str | None) -> bool:
        if not token:
            return False
        now = time.monotonic()
        with self._lock:
            session = self._sessions.get(token)
            if session is None:
                return False
            expires_at, last_used = session
            if not self._is_live(expires_at, last_used, now):
                del self._sessions[token]
                return False
            self._sessions[token] = (expires_at, now)
        return True


def authenticate_api_request(request: Request) -> None:
    """Authenticates a REST API request via the X-API-Key header, applying
    the failed-attempt rate limit.

    Called from RequestGuardMiddleware before the request body is read, so
    unauthenticated clients cannot make the server buffer or parse a body.
    """
    limiter = request.app.state.login_limiter
    key = client_key(request)
    limiter.check(key)
    if not verify_api_key(request.headers.get("x-api-key"), request):
        limiter.record_failure(key)
        raise UnauthorizedError()
    limiter.record_success(key)


def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """Defense in depth for /api/* routes: re-verifies the X-API-Key header.

    The primary check (with rate limiting) runs earlier in
    RequestGuardMiddleware; this only guards against the middleware being
    removed or misconfigured, so it does not touch the rate limiter.
    """
    if not verify_api_key(x_api_key, request):
        raise UnauthorizedError()


class RedirectToLogin(Exception):
    """Raised to send an unauthenticated web screen request to /login."""


def require_web_session(request: Request) -> None:
    """Authenticates SSR screen requests via the session cookie."""
    if not request.app.state.sessions.is_valid(request.cookies.get(SESSION_COOKIE_NAME)):
        raise RedirectToLogin()


def require_same_origin(request: Request) -> None:
    """CSRF protection for state-changing web screen requests.

    Browsers send Origin on every cross-origin POST (and on same-origin
    POSTs in all modern browsers); Referer is used as a fallback. A request
    carrying neither is rejected, since legitimate non-browser clients use
    /api/* with the X-API-Key header instead.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    source = request.headers.get("origin") or request.headers.get("referer")
    if not source or source == "null":
        raise ForbiddenError()
    host = request.headers.get("host", "")
    if urlsplit(source).netloc.lower() != host.lower():
        raise ForbiddenError()
