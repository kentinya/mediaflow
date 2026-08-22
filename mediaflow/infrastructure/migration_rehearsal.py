from __future__ import annotations

import os
import sqlite3
import tempfile
import urllib.parse
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from mediaflow.infrastructure.sqlite_backup import SQLiteBackupService
from mediaflow.infrastructure.sqlite_runtime import SCHEMA_VERSION, SQLiteTaskRepository

CORE_TABLES = ("tasks", "task_results", "security_audit", "operational_logs")


@dataclass(frozen=True)
class MigrationRehearsalResult:
    source_schema: int
    target_schema: int
    migration_required: bool
    migration_performed: bool
    record_counts: tuple[tuple[str, int], ...]
    backup_size_bytes: int
    backup_sha256: str
    temporary_cleanup_complete: bool
    application_version: str
    completed_at: datetime


class SQLiteMigrationRehearsalService:
    def __init__(self, backup: str | Path) -> None:
        raw = os.fspath(backup)
        if not raw or "\0" in raw:
            raise ValueError("migration rehearsal backup path is invalid")
        self._backup = Path(raw).absolute()

    def rehearse(self) -> MigrationRehearsalResult:
        backup = self._backup
        parent = backup.parent
        if not parent.exists() or not parent.is_dir() or parent.is_symlink():
            raise ValueError("migration rehearsal parent must be an existing non-symlink directory")
        verifier = SQLiteBackupService(backup)
        source = verifier.verify(backup)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".mediaflow-migration-rehearsal-", suffix=".sqlite3.tmp", dir=parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        values: dict[str, object] | None = None
        try:
            os.chmod(temporary, 0o600)
            _copy_database(backup, temporary)
            before = _counts(temporary)
            with SQLiteTaskRepository(temporary) as repository:
                target_schema = repository.schema_version
            migrated = verifier.verify(temporary)
            if target_schema != SCHEMA_VERSION or migrated.schema_version != SCHEMA_VERSION:
                raise ValueError("migration rehearsal did not reach the current runtime schema")
            after = _counts(temporary)
            if any(after[name] != count for name, count in before.items()):
                raise ValueError("migration rehearsal changed representative runtime record counts")
            values = {
                "source_schema": source.schema_version,
                "target_schema": target_schema,
                "migration_required": source.schema_version < SCHEMA_VERSION,
                "migration_performed": source.schema_version < target_schema,
                "record_counts": tuple((name, after[name]) for name in CORE_TABLES),
                "backup_size_bytes": source.size_bytes,
                "backup_sha256": source.sha256,
            }
        finally:
            _cleanup(temporary)
        assert values is not None
        return MigrationRehearsalResult(
            **values,
            temporary_cleanup_complete=True,
            application_version=_application_version(),
            completed_at=datetime.now(UTC),
        )


def _copy_database(source: Path, destination: Path) -> None:
    uri = f"file:{urllib.parse.quote(str(source), safe='/')}?mode=ro"
    with (
        closing(sqlite3.connect(uri, uri=True)) as input_connection,
        closing(sqlite3.connect(destination)) as output_connection,
    ):
        input_connection.backup(output_connection)


def _counts(path: Path) -> dict[str, int]:
    uri = f"file:{urllib.parse.quote(str(path), safe='/')}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        existing = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        return {
            table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            if table in existing
            else 0
            for table in CORE_TABLES
        }


def _cleanup(temporary: Path) -> None:
    for path in (
        Path(f"{temporary}-wal"),
        Path(f"{temporary}-shm"),
        Path(f"{temporary}-journal"),
        temporary,
    ):
        if path.exists() or path.is_symlink():
            path.unlink()


def _application_version() -> str:
    try:
        return version("mediaflow")
    except PackageNotFoundError:
        return "development"
