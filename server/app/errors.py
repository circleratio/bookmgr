from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Base class for errors translated into the API's {"error": {...}} shape."""

    status_code = 500
    code = "INTERNAL_ERROR"
    default_message = "internal server error"

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class ValidationError(AppError):
    status_code = 400
    code = "VALIDATION_ERROR"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    default_message = "book not found"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    default_message = "invalid or missing API key"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    default_message = "cross-origin request rejected"


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"
    default_message = "too many attempts, try again later"


class UpstreamError(AppError):
    status_code = 502
    code = "UPSTREAM_ERROR"
    default_message = "failed to fetch book info"


class BodyTooLarge(StarletteHTTPException):
    """Raised by RequestGuardMiddleware's receive wrapper once a streamed
    body exceeds the size limit. It subclasses HTTPException because FastAPI
    re-raises those unchanged while parsing a body (any other exception is
    turned into a generic 400)."""

    def __init__(self) -> None:
        super().__init__(status_code=413, detail="request body too large")


def _describe_validation_errors(exc: RequestValidationError) -> str:
    """Summarizes validation errors by field location and message only,
    without echoing the submitted input values back to the client."""
    parts = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg', 'invalid value')}")
    return "; ".join(parts) or "invalid value"


def register_exception_handlers(app: FastAPI) -> None:
    from .auth import RedirectToLogin

    @app.exception_handler(RedirectToLogin)
    async def handle_redirect_to_login(request: Request, exc: RedirectToLogin) -> RedirectResponse:
        return RedirectResponse("/login", status_code=302)

    @app.exception_handler(BodyTooLarge)
    async def handle_body_too_large(request: Request, exc: BodyTooLarge) -> JSONResponse:
        return JSONResponse(
            status_code=413,
            content={"error": {"code": "PAYLOAD_TOO_LARGE", "message": "request body too large"}},
        )

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"invalid request body: {_describe_validation_errors(exc)}",
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "internal server error"}},
        )
