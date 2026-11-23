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

from mediaflow.infrastructure.sqlite_backup import SQLiteBackupService


@dataclass(frozen=True)
class DatabaseRestoreResult:
    destination: str
    completed_at: datetime
    schema_version: int
    size_bytes: int
    sha256: str
    schema_kind: str
    source: str
    source_sha256: str


class SQLiteRestoreService:
    def __init__(self, backup: str | Path, destination: str | Path) -> None:
        self._backup = _path(backup, "backup")
        self._destination = _path(destination, "destination")

    def restore(self, *, confirmed_empty_destination: bool = False) -> DatabaseRestoreResult:
        if not confirmed_empty_destination:
            raise ValueError("restore requires --confirm-empty-destination")
        backup, target = self._backup, self._destination
        if backup.resolve(strict=False) == target.resolve(strict=False):
            raise ValueError("restore backup and destination must be different files")
        _require_empty_destination(target)
        verifier = SQLiteBackupService(backup)
        verified = verifier.verify(backup)
        _require_startable(verified)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".mediaflow-restore-", suffix=".sqlite3.tmp", dir=target.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            os.chmod(temporary, 0o600)
            _copy_database(backup, temporary)
            staged = verifier.verify(temporary, destination=target)
            _require_startable(staged)
            # The published copy is what the services start from, but the
            # backup stays the operator's preserved original.  Re-checking it
            # before publication keeps the source digest that the restore
            # reports identical to the one it verified.
            _require_source_unchanged(backup, verified.sha256)
            _fsync(temporary)
            _publish(temporary, target)
            temporary.unlink()
            return DatabaseRestoreResult(
                str(target),
                datetime.now(UTC),
                staged.schema_version,
                staged.size_bytes,
                staged.sha256,
                staged.schema_kind,
                str(backup),
                verified.sha256,
            )
        finally:
            if temporary.exists():
                temporary.unlink()


def _require_startable(verified) -> None:
    """Refuse a backup a formal service start would not accept."""

    if not verified.usable:
        raise ValueError(
            f"backup is not usable by this MediaFlow version: {verified.applicability_reason}"
        )


def _require_source_unchanged(backup: Path, expected_sha256: str) -> None:
    digest = hashlib.sha256()
    with backup.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected_sha256:
        raise ValueError(
            "source backup changed during restore; the destination was not published. "
            "Keep the original backup, verify it again and repeat the restore"
        )


def _copy_database(source: Path, destination: Path) -> None:
    source_uri = f"file:{urllib.parse.quote(str(source), safe='/')}?mode=ro"
    with (
        closing(sqlite3.connect(source_uri, uri=True)) as input_connection,
        closing(sqlite3.connect(destination)) as output_connection,
    ):
        input_connection.backup(output_connection)


def _fsync(path: Path) -> None:
    with path.open("rb") as stream:
        os.fsync(stream.fileno())


def _publish(source: Path, destination: Path) -> None:
    try:
        os.link(source, destination)
    except FileExistsError as error:
        raise ValueError("runtime database destination appeared during restore") from error


def _path(value: str | Path, label: str) -> Path:
    raw = os.fspath(value)
    if not raw or "\0" in raw:
        raise ValueError(f"restore {label} path is invalid")
    return Path(raw).absolute()


def _require_empty_destination(target: Path) -> None:
    if target.exists() or target.is_symlink():
        raise ValueError("configured runtime database destination must not exist")
    parent = target.parent
    if not parent.exists() or not parent.is_dir() or parent.is_symlink():
        raise ValueError("restore destination parent must be an existing non-symlink directory")
    for suffix in ("-wal", "-shm", "-journal"):
        if Path(f"{target}{suffix}").exists() or Path(f"{target}{suffix}").is_symlink():
            raise ValueError(f"restore destination sidecar {suffix} already exists")
