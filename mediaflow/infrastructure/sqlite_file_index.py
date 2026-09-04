from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from mediaflow.domain.file_catalog import FileCatalogEnrichedRecord
from mediaflow.domain.file_index import FileIndexRecord, mark_missing
from mediaflow.domain.file_lifecycle import (
    FileIndexLifecycleError,
    FileIndexOccurrence,
    OccurrenceState,
    ProcessingDisposition,
    ReprocessRequest,
    next_action_for_disposition,
)
from mediaflow.domain.scanner import FileChange, FileScanStatus
from mediaflow.domain.task_persistence import PersistentResultRecord
from mediaflow.infrastructure.file_index_schema import (
    ensure_file_index_schema,
    ensure_task_occurrence_columns,
)


class SQLiteFileIndexRepository:
    """Durable FileIndex repository using bounded batch transactions."""

    def __init__(self, database_path: str | Path) -> None:
        self._connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._connection:
            ensure_file_index_schema(self._connection)
            tables = {
                row["name"]
                for row in self._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if {"task_items", "task_results"}.issubset(tables):
                ensure_task_occurrence_columns(self._connection)

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

    def find_by_file_id(
        self, file_id: str, *, resource_library_id: str | None = None
    ) -> FileIndexRecord | None:
        if not isinstance(file_id, str) or not file_id.strip():
            raise ValueError("FileIndex file ID is required")
        with self._lock:
            if resource_library_id is None:
                row = self._connection.execute(
                    "SELECT * FROM file_index WHERE file_id=?", (file_id,)
                ).fetchone()
            else:
                row = self._connection.execute(
                    "SELECT * FROM file_index WHERE file_id=? AND resource_library_id=?",
                    (file_id, resource_library_id),
                ).fetchone()
        return self._record(row) if row is not None else None

    def batch_upsert(self, records: Sequence[FileIndexRecord]) -> None:
        if not records:
            return
        statement = """
            INSERT INTO file_index (
                file_id, storage_id, resource_library_id, path, filename, extension, size,
                modified_at, first_seen_at, last_seen_at, stable_since, scan_status,
                change_status, created_at, updated_at, missing_since, last_scan_id,
                occurrence_id, fingerprint, fingerprint_algorithm, fingerprint_evidence,
                occurrence_state, processing_disposition, processing_result_id,
                processing_effect_certainty, processing_retry_safety, processing_next_action,
                processing_updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(storage_id, resource_library_id, path) DO UPDATE SET
                file_id=excluded.file_id, filename=excluded.filename,
                extension=excluded.extension, size=excluded.size,
                modified_at=excluded.modified_at, first_seen_at=excluded.first_seen_at,
                last_seen_at=excluded.last_seen_at, stable_since=excluded.stable_since,
                scan_status=excluded.scan_status, change_status=excluded.change_status,
                created_at=excluded.created_at, updated_at=excluded.updated_at,
                missing_since=excluded.missing_since, last_scan_id=excluded.last_scan_id,
                occurrence_id=COALESCE(excluded.occurrence_id, file_index.occurrence_id),
                fingerprint=COALESCE(excluded.fingerprint, file_index.fingerprint),
                fingerprint_algorithm=COALESCE(
                    excluded.fingerprint_algorithm, file_index.fingerprint_algorithm
                ),
                fingerprint_evidence=CASE WHEN excluded.occurrence_id IS NULL
                    THEN file_index.fingerprint_evidence ELSE excluded.fingerprint_evidence END,
                occurrence_state=CASE WHEN excluded.occurrence_id IS NULL
                    THEN file_index.occurrence_state ELSE excluded.occurrence_state END,
                processing_disposition=CASE WHEN excluded.occurrence_id IS NULL
                    THEN file_index.processing_disposition ELSE excluded.processing_disposition END,
                processing_result_id=CASE WHEN excluded.occurrence_id IS NULL
                    THEN file_index.processing_result_id ELSE excluded.processing_result_id END,
                processing_effect_certainty=CASE WHEN excluded.occurrence_id IS NULL
                    THEN file_index.processing_effect_certainty
                    ELSE excluded.processing_effect_certainty END,
                processing_retry_safety=CASE WHEN excluded.occurrence_id IS NULL
                    THEN file_index.processing_retry_safety
                    ELSE excluded.processing_retry_safety END,
                processing_next_action=CASE WHEN excluded.occurrence_id IS NULL
                    THEN file_index.processing_next_action ELSE excluded.processing_next_action END,
                processing_updated_at=CASE WHEN excluded.occurrence_id IS NULL
                    THEN file_index.processing_updated_at ELSE excluded.processing_updated_at END
        """
        with self._lock, self._connection:
            for record in records:
                previous_row = self._connection.execute(
                    "SELECT * FROM file_index WHERE storage_id=? "
                    "AND resource_library_id=? AND path=?",
                    record.identity,
                ).fetchone()
                previous = self._record(previous_row) if previous_row is not None else None
                if (
                    previous is not None
                    and record.occurrence_id is not None
                    and record.updated_at < previous.updated_at
                ):
                    record = _reconciliation_conflict(previous)
                if (
                    previous is not None
                    and record.occurrence_id is not None
                    and previous.occurrence_id != record.occurrence_id
                ):
                    self._supersede_occurrence(previous, record.updated_at)
                self._connection.execute(statement, self._values(record))
                if record.occurrence_id is not None:
                    self._sync_occurrence(record)

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
                r.cleanup_step_count AS r_cleanup_step_count,
                r.effect_certainty AS r_effect_certainty,
                r.uncertain_effects AS r_uncertain_effects,
                r.source_occurrence_id AS r_source_occurrence_id,
                r.source_fingerprint AS r_source_fingerprint,
                r.source_fingerprint_state AS r_source_fingerprint_state
            FROM file_index f
            LEFT JOIN task_results r ON r.result_id = (
                SELECT r2.result_id FROM task_results r2
                WHERE r2.source_storage_id = f.storage_id
                  AND r2.source_path = f.path
                  AND (
                      f.occurrence_id IS NULL
                      OR f.occurrence_state = 'legacy'
                      OR (
                          r2.source_occurrence_id = f.occurrence_id
                          AND r2.source_fingerprint = f.fingerprint
                      )
                  )
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

    def occurrence_history(
        self, file_id: str, *, limit: int = 32
    ) -> tuple[FileIndexOccurrence, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("FileIndex occurrence history limit must be between 1 and 100")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM file_index_occurrences
                WHERE file_id=? ORDER BY last_seen_at DESC, occurrence_id DESC LIMIT ?""",
                (file_id, limit),
            ).fetchall()
        return tuple(self._occurrence(row) for row in rows)

    def list_reprocess_requests(
        self, file_id: str, *, limit: int = 32
    ) -> tuple[ReprocessRequest, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("FileIndex Reprocess history limit must be between 1 and 100")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM file_index_reprocess_requests
                WHERE file_id=? ORDER BY requested_at DESC, request_id DESC LIMIT ?""",
                (file_id, limit),
            ).fetchall()
        return tuple(
            ReprocessRequest(
                row["request_id"],
                row["file_id"],
                row["occurrence_id"],
                row["fingerprint"],
                row["actor"],
                datetime.fromisoformat(row["requested_at"]),
                row["status"],
                row["next_action"],
                row["error"],
            )
            for row in rows
        )

    def admit_reprocess(
        self,
        file_id: str,
        occurrence_id: str,
        fingerprint: str,
        *,
        actor: str,
        requested_at: datetime,
    ) -> ReprocessRequest:
        """Atomically admit a bounded request without creating executable work."""

        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("Reprocess actor is required")
        if not isinstance(occurrence_id, str) or not occurrence_id.strip():
            raise ValueError("current occurrence ID is required")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise ValueError("current source fingerprint is required")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT * FROM file_index WHERE file_id=?", (file_id,)
                ).fetchone()
                if row is None:
                    raise FileIndexLifecycleError(
                        "file_not_found",
                        f"FileIndex record {file_id!r} was not found",
                        status=404,
                        next_action="reload the FileIndex list and select a current file",
                    )
                current = self._record(row)
                if current.occurrence_id != occurrence_id:
                    raise FileIndexLifecycleError(
                        "stale_occurrence",
                        "the requested source occurrence is no longer current",
                        next_action=(
                            "reload this FileIndex detail and confirm the current occurrence"
                        ),
                        details={"currentOccurrenceId": current.occurrence_id},
                    )
                if current.fingerprint != fingerprint:
                    raise FileIndexLifecycleError(
                        "stale_fingerprint",
                        "the requested source fingerprint is no longer current",
                        next_action=(
                            "reload this FileIndex detail and confirm the current fingerprint"
                        ),
                    )
                if current.scan_status is not FileScanStatus.READY:
                    raise FileIndexLifecycleError(
                        "source_not_ready",
                        "Reprocess requires a stable ready current source",
                        next_action="run a complete Scan and wait until this source is ready",
                        details={"scanStatus": current.scan_status.value},
                    )
                if current.occurrence_state is not OccurrenceState.VERIFIED:
                    raise FileIndexLifecycleError(
                        "occurrence_unverified",
                        "Reprocess requires verified current source evidence",
                        next_action="run a complete Scan to refresh the source occurrence evidence",
                    )
                active = self._connection.execute(
                    """SELECT request_id FROM file_index_reprocess_requests
                    WHERE file_id=? AND occurrence_id=? AND status='admitted'
                    ORDER BY requested_at DESC LIMIT 1""",
                    (file_id, occurrence_id),
                ).fetchone()
                if active is not None:
                    raise FileIndexLifecycleError(
                        "duplicate_reprocess",
                        "a Reprocess request for this occurrence is already admitted",
                        next_action=(
                            "run the later explicit Scan or Preview admission, or "
                            "inspect the existing request"
                        ),
                        details={"requestId": active["request_id"]},
                    )
                if current.processing_disposition in {
                    ProcessingDisposition.UNKNOWN,
                    ProcessingDisposition.UNVERIFIED,
                    ProcessingDisposition.REPROCESS_REQUESTED,
                }:
                    raise FileIndexLifecycleError(
                        "reprocess_not_eligible",
                        "Reprocess is only available when a prior processing "
                        "disposition can suppress duplicate work",
                        next_action=next_action_for_disposition(current.processing_disposition),
                    )
                if current.processing_retry_safety != "safe":
                    raise FileIndexLifecycleError(
                        "reprocess_not_safe",
                        "Reprocess requires a Result with verified safe-to-repeat effects",
                        next_action="inspect the recorded effects before requesting Reprocess",
                    )
                from uuid import uuid4

                request_id = "reprocess-" + uuid4().hex
                next_action = next_action_for_disposition(ProcessingDisposition.REPROCESS_REQUESTED)
                self._connection.execute(
                    """INSERT INTO file_index_reprocess_requests (
                        request_id, file_id, occurrence_id, fingerprint, actor,
                        requested_at, status, next_action, error
                    ) VALUES (?, ?, ?, ?, ?, ?, 'admitted', ?, NULL)""",
                    (
                        request_id,
                        file_id,
                        occurrence_id,
                        fingerprint,
                        actor,
                        requested_at.isoformat(),
                        next_action,
                    ),
                )
                self._connection.execute(
                    """UPDATE file_index SET processing_disposition=?, processing_updated_at=?,
                        processing_next_action=? WHERE file_id=? AND occurrence_id=?""",
                    (
                        ProcessingDisposition.REPROCESS_REQUESTED.value,
                        requested_at.isoformat(),
                        next_action,
                        file_id,
                        occurrence_id,
                    ),
                )
                self._connection.execute(
                    """UPDATE file_index_occurrences SET processing_disposition=?,
                        processing_updated_at=?, processing_next_action=?
                    WHERE file_id=? AND occurrence_id=?""",
                    (
                        ProcessingDisposition.REPROCESS_REQUESTED.value,
                        requested_at.isoformat(),
                        next_action,
                        file_id,
                        occurrence_id,
                    ),
                )
                self._connection.commit()
                return ReprocessRequest(
                    request_id,
                    file_id,
                    occurrence_id,
                    fingerprint,
                    actor,
                    requested_at,
                    "admitted",
                    next_action,
                )
            except BaseException:
                self._connection.rollback()
                raise

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
            record.occurrence_id,
            record.fingerprint,
            record.fingerprint_algorithm,
            json.dumps(record.fingerprint_evidence or {}, ensure_ascii=False, sort_keys=True),
            record.occurrence_state.value,
            record.processing_disposition.value,
            record.processing_result_id,
            record.processing_effect_certainty,
            record.processing_retry_safety,
            record.processing_next_action,
            record.processing_updated_at.isoformat() if record.processing_updated_at else None,
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
            occurrence_id=row["occurrence_id"] if "occurrence_id" in row.keys() else None,
            fingerprint=row["fingerprint"] if "fingerprint" in row.keys() else None,
            fingerprint_algorithm=(
                row["fingerprint_algorithm"] if "fingerprint_algorithm" in row.keys() else None
            ),
            fingerprint_evidence=(
                json.loads(row["fingerprint_evidence"] or "{}")
                if "fingerprint_evidence" in row.keys()
                else None
            ),
            occurrence_state=(
                OccurrenceState(row["occurrence_state"])
                if "occurrence_state" in row.keys() and row["occurrence_state"]
                else OccurrenceState.LEGACY
            ),
            processing_disposition=(
                ProcessingDisposition(row["processing_disposition"])
                if "processing_disposition" in row.keys() and row["processing_disposition"]
                else ProcessingDisposition.UNKNOWN
            ),
            processing_result_id=(
                row["processing_result_id"] if "processing_result_id" in row.keys() else None
            ),
            processing_effect_certainty=(
                row["processing_effect_certainty"]
                if "processing_effect_certainty" in row.keys()
                else "unknown"
            ),
            processing_retry_safety=(
                row["processing_retry_safety"]
                if "processing_retry_safety" in row.keys()
                else "unknown"
            ),
            processing_next_action=(
                row["processing_next_action"]
                if "processing_next_action" in row.keys()
                else "observe a verified current occurrence, then run explicit analysis"
            ),
            processing_updated_at=(
                optional_time(row["processing_updated_at"])
                if "processing_updated_at" in row.keys()
                else None
            ),
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
            row["r_effect_certainty"] if "r_effect_certainty" in row.keys() else "unknown",
            tuple(json.loads(row["r_uncertain_effects"] or "[]"))
            if "r_uncertain_effects" in row.keys()
            else (),
            row["r_source_occurrence_id"] if "r_source_occurrence_id" in row.keys() else None,
            row["r_source_fingerprint"] if "r_source_fingerprint" in row.keys() else None,
            row["r_source_fingerprint_state"]
            if "r_source_fingerprint_state" in row.keys()
            else "unverified",
        )
        return FileCatalogEnrichedRecord(SQLiteFileIndexRepository._record(row), result)

    def _supersede_occurrence(self, previous: FileIndexRecord, timestamp: datetime) -> None:
        if previous.occurrence_id is None:
            return
        self._connection.execute(
            """UPDATE file_index_occurrences SET is_current=0, superseded_at=?
            WHERE file_id=? AND occurrence_id=?""",
            (timestamp.isoformat(), previous.file_id, previous.occurrence_id),
        )

    def _sync_occurrence(self, record: FileIndexRecord) -> None:
        self._connection.execute(
            """INSERT INTO file_index_occurrences (
                occurrence_id, file_id, storage_id, resource_library_id, path,
                fingerprint, fingerprint_algorithm, fingerprint_evidence, occurrence_state,
                first_seen_at, last_seen_at, is_current, superseded_at,
                processing_disposition, processing_result_id, processing_effect_certainty,
                processing_retry_safety, processing_next_action, processing_updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(occurrence_id) DO UPDATE SET
                file_id=excluded.file_id, storage_id=excluded.storage_id,
                resource_library_id=excluded.resource_library_id, path=excluded.path,
                fingerprint=excluded.fingerprint,
                fingerprint_algorithm=excluded.fingerprint_algorithm,
                fingerprint_evidence=excluded.fingerprint_evidence,
                occurrence_state=excluded.occurrence_state,
                first_seen_at=file_index_occurrences.first_seen_at,
                last_seen_at=excluded.last_seen_at,
                is_current=1, superseded_at=NULL,
                processing_disposition=excluded.processing_disposition,
                processing_result_id=excluded.processing_result_id,
                processing_effect_certainty=excluded.processing_effect_certainty,
                processing_retry_safety=excluded.processing_retry_safety,
                processing_next_action=excluded.processing_next_action,
                processing_updated_at=excluded.processing_updated_at
            """,
            (
                record.occurrence_id,
                record.file_id,
                record.storage_id,
                record.resource_library_id,
                record.path,
                record.fingerprint,
                record.fingerprint_algorithm,
                json.dumps(record.fingerprint_evidence or {}, ensure_ascii=False, sort_keys=True),
                record.occurrence_state.value,
                record.first_seen_at.isoformat(),
                record.last_seen_at.isoformat(),
                1,
                None,
                record.processing_disposition.value,
                record.processing_result_id,
                record.processing_effect_certainty,
                record.processing_retry_safety,
                record.processing_next_action,
                record.processing_updated_at.isoformat() if record.processing_updated_at else None,
            ),
        )

    @staticmethod
    def _occurrence(row: sqlite3.Row) -> FileIndexOccurrence:
        def optional_time(value: str | None) -> datetime | None:
            return datetime.fromisoformat(value) if value else None

        return FileIndexOccurrence(
            row["occurrence_id"],
            row["file_id"],
            row["storage_id"],
            row["resource_library_id"],
            row["path"],
            row["fingerprint"],
            row["fingerprint_algorithm"],
            json.loads(row["fingerprint_evidence"] or "{}"),
            OccurrenceState(row["occurrence_state"]),
            datetime.fromisoformat(row["first_seen_at"]),
            datetime.fromisoformat(row["last_seen_at"]),
            bool(row["is_current"]),
            optional_time(row["superseded_at"]),
            ProcessingDisposition(row["processing_disposition"]),
            row["processing_result_id"],
            row["processing_effect_certainty"],
            row["processing_retry_safety"],
            row["processing_next_action"],
            optional_time(row["processing_updated_at"]),
        )


def _reconciliation_conflict(record: FileIndexRecord) -> FileIndexRecord:
    processing_at = max(record.updated_at, record.processing_updated_at or record.updated_at)
    return replace(
        record,
        processing_disposition=ProcessingDisposition.ATTENTION,
        processing_effect_certainty="unknown",
        processing_retry_safety="unknown",
        processing_next_action=next_action_for_disposition(ProcessingDisposition.ATTENTION),
        processing_updated_at=processing_at,
    )
