from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Settings
from .db import Database
from .errors import register_exception_handlers
from .repositories.book_repository import BookRepository
from .routers.books import router as books_router
from .routers.isbn_lookup import router as isbn_lookup_router
from .services.book_service import BookService
from .services.isbn_lookup_service import ISBNLookupService


def create_app(settings: Settings) -> FastAPI:
    db = Database(settings.db_path, settings.migrations_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        db.close()

    app = FastAPI(lifespan=lifespan)
    app.state.api_key = settings.api_key
    app.state.book_service = BookService(BookRepository(db))
    app.state.isbn_lookup_service = ISBNLookupService(settings.google_books_api_key)

    register_exception_handlers(app)
    app.include_router(books_router, prefix="/api")
    app.include_router(isbn_lookup_router, prefix="/api")

    return app


def main() -> None:
    import uvicorn

    settings = Settings.from_env()
    app = create_app(settings)
    print(f"listening on :{settings.port}")
    uvicorn.run(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
