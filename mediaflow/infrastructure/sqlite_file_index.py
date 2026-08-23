from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from mediaflow.domain.file_catalog import FileCatalogEnrichedRecord
from mediaflow.domain.file_index import FileIndexRecord, mark_missing
from mediaflow.domain.scanner import FileChange, FileScanStatus
from mediaflow.domain.task_persistence import PersistentResultRecord


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

    def list_catalog(
        self,
        resource_library_ids: Sequence[str],
        *,
        storage_id: str | None = None,
        scan_status: FileScanStatus | None = None,
        query: str | None = None,
        limit: int = 100,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[FileIndexRecord, ...]:
        if not resource_library_ids:
            raise ValueError("file catalog requires at least one ResourceLibrary")
        if after is not None and before is not None:
            raise ValueError("file catalog after and before are mutually exclusive")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("file catalog limit must be positive")
        placeholders = ", ".join("?" for _ in resource_library_ids)
        sql = f"""
            SELECT * FROM file_index
            WHERE resource_library_id IN ({placeholders})
        """
        parameters: list[object] = list(resource_library_ids)
        if storage_id is not None:
            sql += " AND storage_id = ?"
            parameters.append(storage_id)
        if scan_status is not None:
            sql += " AND scan_status = ?"
            parameters.append(scan_status.value)
        if query:
            normalized = query.lower()
            sql += " AND (instr(lower(path), ?) > 0 OR instr(lower(filename), ?) > 0)"
            parameters.extend((normalized, normalized))
        if after is not None:
            sql += " AND (updated_at < ? OR (updated_at = ? AND file_id < ?))"
            parameters.extend((after[0].isoformat(), after[0].isoformat(), after[1]))
        elif before is not None:
            sql += " AND (updated_at > ? OR (updated_at = ? AND file_id > ?))"
            parameters.extend((before[0].isoformat(), before[0].isoformat(), before[1]))
        sql += " ORDER BY updated_at DESC, file_id DESC LIMIT ?"
        parameters.append(limit)
        with self._lock:
            rows = self._connection.execute(sql, tuple(parameters)).fetchall()
        return tuple(self._record(row) for row in rows)

    def list_enriched_catalog(
        self,
        resource_library_ids: Sequence[str],
        *,
        storage_id: str | None = None,
        scan_status: FileScanStatus | None = None,
        query: str | None = None,
        limit: int = 100,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
        recognition_type: str | None = None,
        provider: str | None = None,
        provider_id: str | None = None,
        title: str | None = None,
        task_id: str | None = None,
        year: int | None = None,
    ) -> tuple[FileCatalogEnrichedRecord, ...]:
        if not resource_library_ids:
            raise ValueError("file catalog requires at least one ResourceLibrary")
        if after is not None and before is not None:
            raise ValueError("file catalog after and before are mutually exclusive")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("file catalog limit must be positive")
        placeholders = ", ".join("?" for _ in resource_library_ids)
        sql = f"""
            SELECT f.*,
                r.result_id AS r_result_id,
                r.task_id AS r_task_id,
                r.item_id AS r_item_id,
                r.source_storage_id AS r_source_storage_id,
                r.source_path AS r_source_path,
                r.destination_storage_id AS r_destination_storage_id,
                r.destination_path AS r_destination_path,
                r.recognition_type AS r_recognition_type,
                r.provider AS r_provider,
                r.provider_id AS r_provider_id,
                r.metadata_policy_id AS r_metadata_policy_id,
                r.naming_policy_id AS r_naming_policy_id,
                r.classification_policy_id AS r_classification_policy_id,
                r.organize_policy_id AS r_organize_policy_id,
                r.operation AS r_operation,
                r.status AS r_status,
                r.created_at AS r_created_at,
                r.title AS r_title,
                r.error AS r_error,
                r.completed_operations AS r_completed_operations,
                r.attachment_count AS r_attachment_count,
                r.retry_attempts AS r_retry_attempts,
                r.retry_category AS r_retry_category,
                r.cleanup_status AS r_cleanup_status,
                r.cleanup_step_count AS r_cleanup_step_count
            FROM file_index f
            LEFT JOIN task_results r ON r.result_id = (
                SELECT r2.result_id FROM task_results r2
                WHERE r2.source_storage_id = f.storage_id
                  AND r2.source_path = f.path
                ORDER BY r2.created_at DESC, r2.result_id DESC
                LIMIT 1
            )
            WHERE f.resource_library_id IN ({placeholders})
        """
        parameters: list[object] = list(resource_library_ids)
        if storage_id is not None:
            sql += " AND f.storage_id = ?"
            parameters.append(storage_id)
        if scan_status is not None:
            sql += " AND f.scan_status = ?"
            parameters.append(scan_status.value)
        if query:
            normalized = query.lower()
            sql += " AND (instr(lower(f.path), ?) > 0 OR instr(lower(f.filename), ?) > 0)"
            parameters.extend((normalized, normalized))
        if recognition_type:
            sql += " AND r.recognition_type = ?"
            parameters.append(recognition_type)
        if provider:
            sql += " AND r.provider = ?"
            parameters.append(provider)
        if provider_id:
            sql += " AND r.provider_id = ?"
            parameters.append(provider_id)
        if title:
            sql += " AND instr(lower(r.title), ?) > 0"
            parameters.append(title.lower())
        if task_id:
            sql += " AND r.task_id = ?"
            parameters.append(task_id)
        if year is not None:
            sql += " AND instr(r.title, ?) > 0"
            parameters.append(str(year))
        if after is not None:
            sql += " AND (f.updated_at < ? OR (f.updated_at = ? AND f.file_id < ?))"
            parameters.extend((after[0].isoformat(), after[0].isoformat(), after[1]))
        elif before is not None:
            sql += " AND (f.updated_at > ? OR (f.updated_at = ? AND f.file_id > ?))"
            parameters.extend((before[0].isoformat(), before[0].isoformat(), before[1]))
        sql += " ORDER BY f.updated_at DESC, f.file_id DESC LIMIT ?"
        parameters.append(limit)
        with self._lock:
            rows = self._connection.execute(sql, tuple(parameters)).fetchall()
        return tuple(self._enriched_record(row) for row in rows)

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

    @staticmethod
    def _enriched_record(row: sqlite3.Row) -> FileCatalogEnrichedRecord:
        if row["r_result_id"] is None:
            return FileCatalogEnrichedRecord(SQLiteFileIndexRepository._record(row), None)
        result = PersistentResultRecord(
            row["r_result_id"],
            row["r_task_id"],
            row["r_item_id"],
            row["r_source_storage_id"],
            row["r_source_path"],
            row["r_destination_storage_id"],
            row["r_destination_path"],
            row["r_recognition_type"],
            row["r_provider"],
            row["r_provider_id"],
            row["r_metadata_policy_id"],
            row["r_naming_policy_id"],
            row["r_classification_policy_id"],
            row["r_organize_policy_id"],
            row["r_operation"],
            row["r_status"],
            datetime.fromisoformat(row["r_created_at"]),
            row["r_title"],
            row["r_error"],
            tuple(json.loads(row["r_completed_operations"])),
            row["r_attachment_count"],
            row["r_retry_attempts"],
            row["r_retry_category"],
            row["r_cleanup_status"],
            row["r_cleanup_step_count"],
        )
        return FileCatalogEnrichedRecord(SQLiteFileIndexRepository._record(row), result)
