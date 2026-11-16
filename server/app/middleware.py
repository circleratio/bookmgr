from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .auth import SESSION_COOKIE_NAME, authenticate_api_request
from .errors import AppError, BodyTooLarge

# Largest request body accepted. The biggest legitimate payload is a book
# with a 2000-character memo, so 1 MiB leaves ample headroom.
MAX_BODY_BYTES = 1024 * 1024

API_PREFIX = "/api"


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


def _too_large() -> JSONResponse:
    return _error_response(413, "PAYLOAD_TOO_LARGE", "request body too large")


def _is_api_path(path: str) -> bool:
    return path == API_PREFIX or path.startswith(API_PREFIX + "/")


# Web screen requests that may carry a body without a session: the login
# form itself, and logout (which reads no body and is harmless signed out).
_SESSIONLESS_WEB_PATHS = frozenset({"/login", "/logout"})
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _requires_web_session(method: str, path: str) -> bool:
    """True for state-changing web screen requests, whose form body FastAPI
    would otherwise parse before require_web_session runs."""
    return (
        method not in _SAFE_METHODS
        and not _is_api_path(path)
        and path not in _SESSIONLESS_WEB_PATHS
        and not path.startswith("/static/")
    )


class RequestGuardMiddleware:
    """Runs before routing and body parsing (FastAPI parses the body before
    resolving route dependencies), and:

    - authenticates /api/* requests via X-API-Key, and state-changing web
      screen requests via the session cookie (redirecting to /login, as
      require_web_session does), so unauthenticated clients never get their
      body read or validated;
    - caps the request body at MAX_BODY_BYTES, rejecting an oversized
      Content-Length up front and aborting chunked bodies once they exceed it.
    """

    def __init__(self, app: ASGIApp, max_body_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)

        if _is_api_path(scope["path"]):
            try:
                authenticate_api_request(request)
            except AppError as exc:
                await _error_response(exc.status_code, exc.code, exc.message)(scope, receive, send)
                return
        elif _requires_web_session(scope["method"], scope["path"]):
            if not request.app.state.sessions.is_valid(request.cookies.get(SESSION_COOKIE_NAME)):
                await RedirectResponse("/login", status_code=302)(scope, receive, send)
                return

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                await _error_response(400, "BAD_REQUEST", "invalid Content-Length")(
                    scope, receive, send
                )
                return
            if declared > self.max_body_bytes:
                await _too_large()(scope, receive, send)
                return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    raise BodyTooLarge()
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except BodyTooLarge:
            if not response_started:
                await _too_large()(scope, receive, send)


# Security headers sent on every response, so the app is protected even when
# run without Caddy (local development, LAN). Keep in sync with
# deploy/Caddyfile, which sets the same values (plus HSTS) at the edge.
SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
        "connect-src 'self'; form-action 'self'; base-uri 'none'; object-src 'none'; "
        "frame-ancestors 'none'"
    ),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
}

_SECURITY_HEADERS_RAW = [
    (name.lower().encode("latin-1"), value.encode("latin-1"))
    for name, value in SECURITY_HEADERS.items()
]

# Sent on every response except static assets, so book data and screens are
# not kept in browser or proxy caches (e.g. viewable via Back after logout on
# a shared device). Static assets hold no user data and stay cacheable, which
# is why this is not part of SECURITY_HEADERS (mirrored at the Caddy edge for
# all paths).
STATIC_PREFIX = "/static/"
_NO_STORE_RAW = (b"cache-control", b"no-store")


class SecurityHeadersMiddleware:
    """Adds SECURITY_HEADERS to every HTTP response that does not already set
    them, plus Cache-Control: no-store outside STATIC_PREFIX.

    HSTS is intentionally left to the TLS-terminating proxy: the app itself
    speaks plain HTTP and cannot tell whether it is reached over HTTPS.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        no_store = not scope["path"].startswith(STATIC_PREFIX)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers.extend(h for h in _SECURITY_HEADERS_RAW if h[0] not in present)
                if no_store and _NO_STORE_RAW[0] not in present:
                    headers.append(_NO_STORE_RAW)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
