from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from mediaflow.domain.file_index import FileIndexRecord, mark_missing
from mediaflow.domain.file_lifecycle import (
    FileIndexLifecycleError,
    FileIndexOccurrence,
    OccurrenceState,
    ProcessingDisposition,
    ReprocessRequest,
    disposition_for_result,
    next_action_for_disposition,
    retry_safety_for_effect_certainty,
)
from mediaflow.domain.scanner import FileScanStatus


class InMemoryFileIndexRepository:
    """Thread-safe test/bootstrap repository; production databases can implement the same port."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], FileIndexRecord] = {}
        self._occurrences: dict[tuple[str, str], FileIndexOccurrence] = {}
        self._reprocess_requests: set[tuple[str, str]] = set()
        self._reprocess_values: list[ReprocessRequest] = []
        self._lock = threading.RLock()
        self.batch_sizes: list[int] = []

    def find_by_path(
        self, storage_id: str, resource_library_id: str, path: str
    ) -> FileIndexRecord | None:
        with self._lock:
            return self._records.get((storage_id, resource_library_id, path))

    def batch_upsert(self, records: Sequence[FileIndexRecord]) -> None:
        with self._lock:
            self.batch_sizes.append(len(records))
            for record in records:
                previous = self._records.get(record.identity)
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
                    self._supersede(previous, record.updated_at)
                self._records[record.identity] = record
                if record.occurrence_id is not None:
                    self._sync_occurrence(record)

    def list_by_resource_library(self, resource_library_id: str) -> Sequence[FileIndexRecord]:
        with self._lock:
            return tuple(
                record
                for record in self._records.values()
                if record.resource_library_id == resource_library_id
            )

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
        allowed_libraries = set(resource_library_ids)
        normalized_query = " ".join(query.split()).lower() if query else None
        with self._lock:
            records = list(self._records.values())
        records = [
            record
            for record in records
            if record.resource_library_id in allowed_libraries
            and (storage_id is None or record.storage_id == storage_id)
            and (scan_status is None or record.scan_status is scan_status)
            and (
                normalized_query is None
                or normalized_query in record.path.lower()
                or normalized_query in record.filename.lower()
            )
            and (after is None or (record.updated_at, record.file_id) < after)
            and (before is None or (record.updated_at, record.file_id) > before)
        ]
        records.sort(key=lambda record: (record.updated_at, record.file_id), reverse=True)
        return tuple(records[:limit])

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
            for identity, record in tuple(self._records.items()):
                if (
                    record.resource_library_id != resource_library_id
                    or record.last_scan_id == scan_id
                ):
                    continue
                if any(
                    record.path == prefix or record.path.startswith(prefix + "/")
                    for prefix in prefixes
                ):
                    continue
                self._records[identity] = mark_missing(record, missing_at)
                changed += 1
        return changed

    def snapshot(self) -> tuple[FileIndexRecord, ...]:
        with self._lock:
            return tuple(self._records.values())

    def find_by_file_id(
        self, file_id: str, *, resource_library_id: str | None = None
    ) -> FileIndexRecord | None:
        with self._lock:
            return next(
                (
                    record
                    for record in self._records.values()
                    if record.file_id == file_id
                    and (
                        resource_library_id is None
                        or record.resource_library_id == resource_library_id
                    )
                ),
                None,
            )

    def occurrence_history(
        self, file_id: str, *, limit: int = 32
    ) -> tuple[FileIndexOccurrence, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("FileIndex occurrence history limit must be between 1 and 100")
        with self._lock:
            values = [
                value
                for (current_file, _), value in self._occurrences.items()
                if current_file == file_id
            ]
        values.sort(key=lambda value: (value.last_seen_at, value.occurrence_id), reverse=True)
        return tuple(values[:limit])

    def admit_reprocess(
        self,
        file_id: str,
        occurrence_id: str,
        fingerprint: str,
        *,
        actor: str,
        requested_at: datetime,
    ) -> ReprocessRequest:
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("Reprocess actor is required")
        if not isinstance(occurrence_id, str) or not occurrence_id.strip():
            raise ValueError("current occurrence ID is required")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise ValueError("current source fingerprint is required")
        with self._lock:
            current = self.find_by_file_id(file_id)
            if current is None:
                raise FileIndexLifecycleError(
                    "file_not_found",
                    f"FileIndex record {file_id!r} was not found",
                    status=404,
                    next_action="reload the FileIndex list and select a current file",
                )
            if current.occurrence_id != occurrence_id:
                raise FileIndexLifecycleError(
                    "stale_occurrence",
                    "the requested source occurrence is no longer current",
                    next_action="reload this FileIndex detail and confirm the current occurrence",
                    details={"currentOccurrenceId": current.occurrence_id},
                )
            if current.fingerprint != fingerprint:
                raise FileIndexLifecycleError(
                    "stale_fingerprint",
                    "the requested source fingerprint is no longer current",
                    next_action="reload this FileIndex detail and confirm the current fingerprint",
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
            if (file_id, occurrence_id) in self._reprocess_requests:
                raise FileIndexLifecycleError(
                    "duplicate_reprocess",
                    "a Reprocess request for this occurrence is already admitted",
                    next_action=(
                        "run the later explicit Scan or Preview admission, or inspect "
                        "the existing request"
                    ),
                )
            if current.processing_disposition in {
                ProcessingDisposition.UNKNOWN,
                ProcessingDisposition.UNVERIFIED,
                ProcessingDisposition.REPROCESS_REQUESTED,
            }:
                raise FileIndexLifecycleError(
                    "reprocess_not_eligible",
                    "Reprocess is only available when a prior processing disposition "
                    "can suppress duplicate work",
                    next_action=next_action_for_disposition(current.processing_disposition),
                )
            if current.processing_retry_safety != "safe":
                raise FileIndexLifecycleError(
                    "reprocess_not_safe",
                    "Reprocess requires a Result with verified safe-to-repeat effects",
                    next_action="inspect the recorded effects before requesting Reprocess",
                )
            self._reprocess_requests.add((file_id, occurrence_id))
            updated = replace(
                current,
                processing_disposition=ProcessingDisposition.REPROCESS_REQUESTED,
                processing_updated_at=requested_at,
                processing_next_action=next_action_for_disposition(
                    ProcessingDisposition.REPROCESS_REQUESTED
                ),
            )
            self._records[current.identity] = updated
            self._sync_occurrence(updated)
            request = ReprocessRequest(
                "reprocess-" + __import__("uuid").uuid4().hex,
                file_id,
                occurrence_id,
                fingerprint,
                actor,
                requested_at,
                "admitted",
                updated.processing_next_action,
            )
            self._reprocess_values.append(request)
            return request

    def list_reprocess_requests(
        self, file_id: str, *, limit: int = 32
    ) -> tuple[ReprocessRequest, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("FileIndex Reprocess history limit must be between 1 and 100")
        with self._lock:
            values = [value for value in self._reprocess_values if value.file_id == file_id]
        return tuple(values[-limit:][::-1])

    def apply_result(self, result) -> None:
        """Apply a Result only to the exact occurrence it observed."""

        occurrence_id = getattr(result, "source_occurrence_id", None)
        fingerprint = getattr(result, "source_fingerprint", None)
        if not occurrence_id or not fingerprint:
            return
        with self._lock:
            current = next(
                (
                    record
                    for record in self._records.values()
                    if record.occurrence_id == occurrence_id
                    and record.fingerprint == fingerprint
                    and record.storage_id == result.source_storage_id
                    and record.path == result.source_path
                ),
                None,
            )
            if (
                current is None
                or current.occurrence_id != occurrence_id
                or current.fingerprint != fingerprint
            ):
                return
            if (
                current.processing_updated_at is not None
                and result.created_at < current.processing_updated_at
            ):
                return
            source_state = str(
                getattr(getattr(result, "source_fingerprint_state", None), "value", "")
                or "unverified"
            ).lower()
            disposition = (
                disposition_for_result(result)
                if source_state == "verified"
                else ProcessingDisposition.UNVERIFIED
            )
            if disposition is ProcessingDisposition.UNKNOWN:
                return
            certainty = str(getattr(result, "effect_certainty", "unknown") or "unknown")
            updated = replace(
                current,
                processing_disposition=disposition,
                processing_result_id=result.result_id,
                processing_effect_certainty=certainty,
                processing_retry_safety=retry_safety_for_effect_certainty(certainty),
                processing_next_action=next_action_for_disposition(disposition),
                processing_updated_at=result.created_at,
            )
            self._records[current.identity] = updated
            self._sync_occurrence(updated)

    def _supersede(self, previous: FileIndexRecord, timestamp: datetime) -> None:
        if previous.occurrence_id is None:
            return
        key = (previous.file_id, previous.occurrence_id)
        value = self._occurrences.get(key)
        if value is not None:
            self._occurrences[key] = replace(value, is_current=False, superseded_at=timestamp)

    def _sync_occurrence(self, record: FileIndexRecord) -> None:
        existing = self._occurrences.get((record.file_id, record.occurrence_id))
        value = FileIndexOccurrence(
            record.occurrence_id,
            record.file_id,
            record.storage_id,
            record.resource_library_id,
            record.path,
            record.fingerprint,
            record.fingerprint_algorithm,
            dict(record.fingerprint_evidence or {}),
            record.occurrence_state,
            existing.first_seen_at if existing is not None else record.updated_at,
            record.last_seen_at,
            True,
            None,
            record.processing_disposition,
            record.processing_result_id,
            record.processing_effect_certainty,
            record.processing_retry_safety,
            record.processing_next_action,
            record.processing_updated_at,
        )
        self._occurrences[(record.file_id, record.occurrence_id)] = value


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
