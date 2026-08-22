import os
from dataclasses import dataclass
from pathlib import Path

# server/app/config.py -> repo root is two levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = str(REPO_ROOT / "db" / "bookmgr.db")
DEFAULT_MIGRATIONS_DIR = str(REPO_ROOT / "db" / "migrations")


@dataclass
class Settings:
    api_key: str
    port: int = 8080
    db_path: str = DEFAULT_DB_PATH
    migrations_dir: str = DEFAULT_MIGRATIONS_DIR
    google_books_api_key: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        api_key = os.environ.get("API_KEY")
        if not api_key:
            raise RuntimeError("API_KEY environment variable is required")
        return cls(
            api_key=api_key,
            port=int(os.environ.get("PORT", "8080")),
            db_path=os.environ.get("DB_PATH", DEFAULT_DB_PATH),
            google_books_api_key=os.environ.get("GOOGLE_BOOKS_API_KEY", ""),
        )
