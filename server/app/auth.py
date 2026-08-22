from fastapi import Header, Request

from .errors import UnauthorizedError

SESSION_COOKIE_NAME = "session"


def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """Authenticates REST API requests via the X-API-Key header."""
    if x_api_key != request.app.state.api_key:
        raise UnauthorizedError()


class RedirectToLogin(Exception):
    """Raised to send an unauthenticated web screen request to /login."""


def require_web_session(request: Request) -> None:
    """Authenticates SSR screen requests via the session cookie."""
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie != request.app.state.api_key:
        raise RedirectToLogin()
