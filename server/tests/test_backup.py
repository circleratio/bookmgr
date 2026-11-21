import datetime
import sqlite3
import stat
from pathlib import Path

import pytest

from app import backup as backup_mod
from app.backup import BackupError, backup
from app.db import Database
from tests.conftest import MIGRATIONS_DIR


@pytest.fixture
def db_file(tmp_path: Path) -> Path:
    path = tmp_path / "bookmgr.db"
    database = Database(str(path), MIGRATIONS_DIR)
    database.conn.execute("INSERT INTO books (title, author) VALUES ('Backup test', 'Tester')")
    database.conn.commit()
    database.close()
    return path


def _at(second: int) -> datetime.datetime:
    return datetime.datetime(2026, 11, 21, 3, 45, second)


def test_backup_copies_database(db_file: Path, tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"

    dest, removed = backup(db_file, backup_dir, keep=3, now=_at(0))

    assert dest == backup_dir / "bookmgr-20261121-034500.db"
    assert removed == []
    conn = sqlite3.connect(dest)
    try:
        titles = [row[0] for row in conn.execute("SELECT title FROM books")]
    finally:
        conn.close()
    assert titles == ["Backup test"]
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    assert stat.S_IMODE(backup_dir.stat().st_mode) == 0o700


def test_backup_keeps_newest(db_file: Path, tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"

    for second in range(4):
        backup(db_file, backup_dir, keep=2, now=_at(second))

    names = sorted(p.name for p in backup_dir.iterdir())
    assert names == ["bookmgr-20261121-034502.db", "bookmgr-20261121-034503.db"]


def test_backup_removes_stale_tmp_files(db_file: Path, tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    stale = backup_dir / "bookmgr-20261120-034500.db.tmp"
    stale.write_bytes(b"partial")

    backup(db_file, backup_dir, keep=2, now=_at(0))

    assert not stale.exists()


def test_backup_ignores_unrelated_files(db_file: Path, tmp_path: Path) -> None:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    other = backup_dir / "manual-copy.db"
    other.write_bytes(b"keep me")

    for second in range(3):
        backup(db_file, backup_dir, keep=1, now=_at(second))

    assert other.exists()


def test_backup_rejects_missing_database(tmp_path: Path) -> None:
    with pytest.raises(BackupError, match="database not found"):
        backup(tmp_path / "missing.db", tmp_path / "backups")


def test_backup_rejects_invalid_keep(db_file: Path, tmp_path: Path) -> None:
    with pytest.raises(BackupError, match="BACKUP_KEEP"):
        backup(db_file, tmp_path / "backups", keep=0)


def test_main_reads_environment(
    db_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    backup_dir = tmp_path / "out"
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))
    monkeypatch.setenv("BACKUP_KEEP", "5")

    assert backup_mod.main() == 0

    files = list(backup_dir.glob("bookmgr-*.db"))
    assert len(files) == 1
    assert "backup written" in capsys.readouterr().out


def test_main_fails_on_bad_keep(
    db_file: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setenv("BACKUP_KEEP", "abc")

    assert backup_mod.main() == 1
    assert "backup failed" in capsys.readouterr().err
