from fastapi import Header, Request

from .errors import UnauthorizedError


def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """Authenticates REST API requests via the X-API-Key header."""
    if x_api_key != request.app.state.api_key:
        raise UnauthorizedError()
