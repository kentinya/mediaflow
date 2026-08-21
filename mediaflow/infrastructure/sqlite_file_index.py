from __future__ import annotations

import sqlite3
import threading
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from mediaflow.domain.file_index import FileIndexRecord, mark_missing
from mediaflow.domain.scanner import FileChange, FileScanStatus


class SQLiteFileIndexRepository:
    """Durable FileIndex repository using bounded batch transactions."""

    def __init__(self, database_path: str | Path) -> None:
        self._connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS file_index (
                    file_id TEXT PRIMARY KEY,
                    storage_id TEXT NOT NULL,
                    resource_library_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    modified_at TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    stable_since TEXT,
                    scan_status TEXT NOT NULL,
                    change_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    missing_since TEXT,
                    last_scan_id TEXT,
                    UNIQUE(storage_id, resource_library_id, path)
                )
                """
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> SQLiteFileIndexRepository:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def find_by_path(
        self, storage_id: str, resource_library_id: str, path: str
    ) -> FileIndexRecord | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT * FROM file_index
                WHERE storage_id = ? AND resource_library_id = ? AND path = ?
                """,
                (storage_id, resource_library_id, path),
            ).fetchone()
        return self._record(row) if row is not None else None

    def batch_upsert(self, records: Sequence[FileIndexRecord]) -> None:
        if not records:
            return
        statement = """
            INSERT INTO file_index VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(storage_id, resource_library_id, path) DO UPDATE SET
                file_id=excluded.file_id, filename=excluded.filename,
                extension=excluded.extension, size=excluded.size,
                modified_at=excluded.modified_at, first_seen_at=excluded.first_seen_at,
                last_seen_at=excluded.last_seen_at, stable_since=excluded.stable_since,
                scan_status=excluded.scan_status, change_status=excluded.change_status,
                created_at=excluded.created_at, updated_at=excluded.updated_at,
                missing_since=excluded.missing_since, last_scan_id=excluded.last_scan_id
        """
        values = tuple(self._values(record) for record in records)
        with self._lock, self._connection:
            self._connection.executemany(statement, values)

    def list_by_resource_library(self, resource_library_id: str) -> Sequence[FileIndexRecord]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM file_index WHERE resource_library_id = ? ORDER BY path",
                (resource_library_id,),
            ).fetchall()
        return tuple(self._record(row) for row in rows)

    def reconcile_missing(
        self,
        resource_library_id: str,
        scan_id: str,
        missing_at: datetime,
        *,
        protected_prefixes: Sequence[str] = (),
    ) -> int:
        prefixes = tuple(prefix.rstrip("/") for prefix in protected_prefixes)
        changed = 0
        with self._lock:
            cursor = self._connection.execute(
                """
                SELECT * FROM file_index
                WHERE resource_library_id = ?
                  AND (last_scan_id IS NULL OR last_scan_id != ?)
                """,
                (resource_library_id, scan_id),
            )
            while rows := cursor.fetchmany(500):
                missing = []
                for row in rows:
                    record = self._record(row)
                    if any(
                        record.path == prefix or record.path.startswith(prefix + "/")
                        for prefix in prefixes
                    ):
                        continue
                    missing.append(mark_missing(record, missing_at))
                if missing:
                    self.batch_upsert(missing)
                    changed += len(missing)
        return changed

    @staticmethod
    def _values(record: FileIndexRecord) -> tuple[object, ...]:
        return (
            record.file_id,
            record.storage_id,
            record.resource_library_id,
            record.path,
            record.filename,
            record.extension,
            record.size,
            record.modified_at.isoformat(),
            record.first_seen_at.isoformat(),
            record.last_seen_at.isoformat(),
            record.stable_since.isoformat() if record.stable_since else None,
            record.scan_status.value,
            record.change.value,
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
            record.missing_since.isoformat() if record.missing_since else None,
            record.last_scan_id,
        )

    @staticmethod
    def _record(row: sqlite3.Row) -> FileIndexRecord:
        def optional_time(value: str | None) -> datetime | None:
            return datetime.fromisoformat(value) if value else None

        return FileIndexRecord(
            file_id=row["file_id"],
            storage_id=row["storage_id"],
            resource_library_id=row["resource_library_id"],
            path=row["path"],
            filename=row["filename"],
            extension=row["extension"],
            size=row["size"],
            modified_at=datetime.fromisoformat(row["modified_at"]),
            first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
            last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
            stable_since=optional_time(row["stable_since"]),
            scan_status=FileScanStatus(row["scan_status"]),
            change=FileChange(row["change_status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            missing_since=optional_time(row["missing_since"]),
            last_scan_id=row["last_scan_id"],
        )
