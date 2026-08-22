from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
import urllib.parse
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION


@dataclass(frozen=True)
class DatabaseBackupResult:
    destination: str
    created_at: datetime
    schema_version: int
    size_bytes: int
    sha256: str


class SQLiteBackupService:
    def __init__(self, source: str | Path) -> None:
        self._source = _path(source, "source")

    def backup(self, destination: str | Path) -> DatabaseBackupResult:
        source = self._source
        target = _path(destination, "destination")
        _require_source(source)
        _require_target(source, target)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".mediaflow-backup-", suffix=".sqlite3.tmp", dir=target.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            with (
                closing(_read_only(source)) as source_connection,
                closing(sqlite3.connect(temporary)) as output,
            ):
                source_connection.backup(output)
            result = self.verify(temporary, destination=target)
            with temporary.open("rb") as stream:
                os.fsync(stream.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError as error:
                raise ValueError("backup destination already exists") from error
            temporary.unlink()
            return result
        finally:
            if temporary.exists():
                temporary.unlink()

    def verify(
        self, candidate: str | Path, *, destination: str | Path | None = None
    ) -> DatabaseBackupResult:
        path = _path(candidate, "backup")
        if not path.exists() or not path.is_file() or path.is_symlink():
            raise ValueError("backup must be an existing regular non-symlink file")
        try:
            with closing(_read_only(path)) as connection:
                integrity = connection.execute("PRAGMA integrity_check(1)").fetchone()
                if integrity is None or integrity[0] != "ok":
                    raise ValueError("backup failed SQLite integrity check")
                marker = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
                ).fetchone()
                row = (
                    connection.execute(
                        "SELECT version FROM schema_version WHERE component='runtime'"
                    ).fetchone()
                    if marker
                    else None
                )
        except sqlite3.Error as error:
            raise ValueError("backup is not a valid MediaFlow SQLite database") from error
        if row is None or isinstance(row[0], bool) or not isinstance(row[0], int):
            raise ValueError("backup is missing the MediaFlow runtime schema marker")
        version = int(row[0])
        if version > SCHEMA_VERSION:
            raise ValueError("backup schema is newer than this MediaFlow version")
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(block)
                digest.update(block)
        if size == 0:
            raise ValueError("backup is empty")
        return DatabaseBackupResult(
            str(destination or path), datetime.now(UTC), version, size, digest.hexdigest()
        )


def _read_only(path: Path) -> sqlite3.Connection:
    uri = f"file:{urllib.parse.quote(str(path), safe='/')}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _path(value: str | Path, label: str) -> Path:
    raw = os.fspath(value)
    if not raw or "\0" in raw:
        raise ValueError(f"backup {label} path is invalid")
    return Path(raw).absolute()


def _require_source(source: Path) -> None:
    if not source.exists() or not source.is_file():
        raise ValueError("configured runtime database does not exist")


def _require_target(source: Path, target: Path) -> None:
    if source.resolve() == target.resolve(strict=False):
        raise ValueError("backup destination must differ from source")
    if target.exists() or target.is_symlink():
        raise ValueError("backup destination already exists")
    parent = target.parent
    if not parent.exists() or not parent.is_dir() or parent.is_symlink():
        raise ValueError("backup destination parent must be an existing non-symlink directory")
