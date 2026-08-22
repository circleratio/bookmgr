from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.repositories.book_repository import BookRepository

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = str(REPO_ROOT / "db" / "migrations")
TEST_API_KEY = "test-api-key"


@pytest.fixture
def db() -> Database:
    database = Database(":memory:", MIGRATIONS_DIR)
    yield database
    database.close()


@pytest.fixture
def book_repo(db: Database) -> BookRepository:
    return BookRepository(db)


@pytest.fixture
def client() -> TestClient:
    settings = Settings(
        api_key=TEST_API_KEY,
        db_path=":memory:",
        migrations_dir=MIGRATIONS_DIR,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def auth_headers() -> dict:
    return {"X-API-Key": TEST_API_KEY}
