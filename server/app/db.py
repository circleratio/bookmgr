import sqlite3
import threading
from pathlib import Path

# Migration files to apply on startup, in order. Kept as a simple ordered
# list since migrations use CREATE TABLE/INDEX IF NOT EXISTS and are safe
# to re-run, mirroring internal/repository/db.go on the Go side.
MIGRATION_FILES = ["0001_create_books.sql"]


class Database:
    """A single shared SQLite connection, serialized with a lock.

    SQLite does not support concurrent writers, and FastAPI runs sync
    endpoints in a thread pool, so every access is serialized through this
    lock rather than opening multiple connections (same rationale as the Go
    server's db.SetMaxOpenConns(1)).
    """

    def __init__(self, db_path: str, migrations_dir: str):
        if db_path != ":memory:":
            parent = Path(db_path).parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()

        with self.lock:
            self.conn.execute("PRAGMA foreign_keys = ON")
            self._migrate(migrations_dir)

    def _migrate(self, migrations_dir: str) -> None:
        for name in MIGRATION_FILES:
            path = Path(migrations_dir) / name
            sql = path.read_text(encoding="utf-8")
            self.conn.executescript(sql)
            self.conn.commit()

    def close(self) -> None:
        self.conn.close()
