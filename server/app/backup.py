"""Back up the bookmgr database with the SQLite online backup API.

Run with ``python -m app.backup`` from the server directory.

Environment variables:
    DB_PATH        database to back up (default: same as the server)
    BACKUP_DIR     output directory (default: backups/ next to the database)
    BACKUP_KEEP    number of backups to keep (default: 14)
"""

import datetime
import os
import sqlite3
import sys
from pathlib import Path

from app.config import DEFAULT_DB_PATH

PREFIX = "bookmgr-"
SUFFIX = ".db"
DEFAULT_KEEP = 14


class BackupError(Exception):
    """Raised when a backup cannot be taken or fails verification."""


def backup(
    db_path: Path,
    backup_dir: Path,
    keep: int = DEFAULT_KEEP,
    now: datetime.datetime | None = None,
) -> tuple[Path, list[Path]]:
    """Write a verified copy of db_path into backup_dir and prune old copies.

    Returns the new backup file and the list of removed old backups.
    """
    if keep < 1:
        raise BackupError("BACKUP_KEEP must be 1 or more")
    if not db_path.is_file():
        raise BackupError(f"database not found: {db_path}")

    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    stamp = (now or datetime.datetime.now()).strftime("%Y%m%d-%H%M%S")
    dest = backup_dir / f"{PREFIX}{stamp}{SUFFIX}"
    tmp = dest.with_name(dest.name + ".tmp")

    # Open the source read-only so the backup job can never modify it.
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
            result = dst.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            dst.close()
    finally:
        src.close()

    if result != "ok":
        tmp.unlink(missing_ok=True)
        raise BackupError(f"integrity check failed: {result}")

    os.chmod(tmp, 0o600)
    # Publish the backup atomically so a half-written file is never kept.
    tmp.replace(dest)

    # Remove leftovers of interrupted runs and backups beyond the retention count.
    for stale in backup_dir.glob(f"{PREFIX}*{SUFFIX}.tmp"):
        stale.unlink(missing_ok=True)
    backups = sorted(backup_dir.glob(f"{PREFIX}*{SUFFIX}"))
    removed = backups[:-keep]
    for old in removed:
        old.unlink()
    return dest, removed


def main() -> int:
    os.umask(0o077)
    db_path = Path(os.environ.get("DB_PATH", DEFAULT_DB_PATH))
    backup_dir = Path(os.environ.get("BACKUP_DIR", db_path.parent / "backups"))
    try:
        keep = int(os.environ.get("BACKUP_KEEP", str(DEFAULT_KEEP)))
        dest, removed = backup(db_path, backup_dir, keep)
    except (BackupError, ValueError, sqlite3.Error, OSError) as exc:
        print(f"backup failed: {exc}", file=sys.stderr)
        return 1
    print(f"backup written: {dest}")
    for old in removed:
        print(f"backup removed: {old}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
