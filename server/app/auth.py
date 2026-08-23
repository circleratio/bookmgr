import secrets
import time

from fastapi import Header, Request

from .errors import UnauthorizedError

SESSION_COOKIE_NAME = "session"
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def verify_api_key(candidate: str | None, request: Request) -> bool:
    if candidate is None:
        return False
    return secrets.compare_digest(candidate, request.app.state.api_key)


def create_session(request: Request) -> str:
    """Issue a random session token, independent of the API key itself."""
    token = secrets.token_urlsafe(32)
    request.app.state.sessions[token] = time.monotonic() + SESSION_TTL_SECONDS
    return token


def revoke_session(request: Request, token: str | None) -> None:
    if token:
        request.app.state.sessions.pop(token, None)


def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """Authenticates REST API requests via the X-API-Key header."""
    request.app.state.login_limiter.check(client_key(request))
    if not verify_api_key(x_api_key, request):
        request.app.state.login_limiter.record_failure(client_key(request))
        raise UnauthorizedError()
    request.app.state.login_limiter.record_success(client_key(request))


class RedirectToLogin(Exception):
    """Raised to send an unauthenticated web screen request to /login."""


def require_web_session(request: Request) -> None:
    """Authenticates SSR screen requests via the session cookie."""
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    expires_at = request.app.state.sessions.get(cookie) if cookie else None
    if expires_at is None or expires_at < time.monotonic():
        raise RedirectToLogin()
