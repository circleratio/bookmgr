from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .auth import authenticate_api_request
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


class RequestGuardMiddleware:
    """Runs before routing and body parsing (FastAPI parses the body before
    resolving route dependencies), and:

    - authenticates /api/* requests via X-API-Key, so unauthenticated
      clients never get their body read or validated;
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
