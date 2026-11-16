import ipaddress
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import Settings
from .db import Database
from .errors import register_exception_handlers
from .middleware import RequestGuardMiddleware, SecurityHeadersMiddleware
from .auth import SessionStore
from .rate_limit import LoginRateLimiter
from .repositories.book_repository import BookRepository
from .routers.books import router as books_router
from .routers.isbn_lookup import router as isbn_lookup_router
from .routers.web_auth import router as web_auth_router
from .routers.web_books import router as web_books_router
from .services.book_service import BookService
from .services.isbn_lookup_service import ISBNLookupService
from .template_helpers import stars


def create_app(settings: Settings) -> FastAPI:
    db = Database(settings.db_path, settings.migrations_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        db.close()

    # The interactive docs and OpenAPI schema are not behind authentication,
    # so they are disabled to avoid exposing the API surface publicly.
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.api_key = settings.api_key
    app.state.cookie_secure = settings.cookie_secure
    app.state.sessions = SessionStore()
    app.state.login_limiter = LoginRateLimiter()
    app.state.book_service = BookService(BookRepository(db))
    app.state.isbn_lookup_service = ISBNLookupService(settings.google_books_api_key)

    templates = Jinja2Templates(directory=settings.templates_dir)
    templates.env.globals["stars"] = stars
    app.state.templates = templates
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    register_exception_handlers(app)
    app.add_middleware(RequestGuardMiddleware)
    # Added last so it is outermost and also covers RequestGuardMiddleware's
    # early 401/413 responses.
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(books_router, prefix="/api")
    app.include_router(isbn_lookup_router, prefix="/api")
    app.include_router(web_auth_router)
    app.include_router(web_books_router)

    return app


def cookie_secure_warning(settings: Settings) -> str | None:
    """Returns a startup warning when the server listens beyond loopback
    without COOKIE_SECURE, i.e. likely serves the session cookie over plain
    HTTP to remote clients. Behind Caddy (HOST=127.0.0.1) the cookie is made
    Secure per request instead (see web_auth._cookie_secure)."""
    if settings.cookie_secure or _is_loopback_host(settings.host):
        return None
    return (
        f"HOST={settings.host} accepts remote connections but COOKIE_SECURE is not set; "
        "the session cookie is sent without the Secure attribute over plain HTTP. "
        "Serve over HTTPS (e.g. behind Caddy) and set COOKIE_SECURE=true."
    )


def _is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main() -> None:
    import uvicorn

    settings = Settings.from_env()
    warning = cookie_secure_warning(settings)
    if warning:
        print(f"WARNING: {warning}", file=sys.stderr)
    app = create_app(settings)
    print(f"listening on {settings.host}:{settings.port}")
    uvicorn.run(app, host=settings.host, port=settings.port, access_log=settings.access_log)


if __name__ == "__main__":
    main()
