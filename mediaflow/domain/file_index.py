from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

from mediaflow.domain.file_lifecycle import (
    OccurrenceState,
    ProcessingDisposition,
)
from mediaflow.domain.scanner import FileChange, FileScanStatus


@dataclass(frozen=True)
class FileIndexRecord:
    file_id: str
    storage_id: str
    resource_library_id: str
    path: str
    filename: str
    extension: str
    size: int
    modified_at: datetime
    first_seen_at: datetime
    last_seen_at: datetime
    stable_since: datetime | None
    scan_status: FileScanStatus
    change: FileChange
    created_at: datetime
    updated_at: datetime
    missing_since: datetime | None = None
    last_scan_id: str | None = None
    # Location identity remains (Storage, ResourceLibrary, relative path).  These fields
    # describe the currently observed source occurrence and are intentionally orthogonal to
    # scan_status/change.
    occurrence_id: str | None = None
    fingerprint: str | None = None
    fingerprint_algorithm: str | None = None
    fingerprint_evidence: dict[str, object] | None = None
    occurrence_state: OccurrenceState = OccurrenceState.LEGACY
    processing_disposition: ProcessingDisposition = ProcessingDisposition.UNKNOWN
    processing_result_id: str | None = None
    processing_effect_certainty: str = "unknown"
    processing_retry_safety: str = "unknown"
    processing_next_action: str = (
        "observe a verified current occurrence, then run explicit analysis"
    )
    processing_updated_at: datetime | None = None

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.storage_id, self.resource_library_id, self.path

    @property
    def source_occurrence_id(self) -> str | None:
        return self.occurrence_id

    @property
    def source_fingerprint(self) -> str | None:
        return self.fingerprint

    @property
    def scan_discovery_status(self) -> FileScanStatus:
        return self.scan_status

    @property
    def processing_status(self) -> ProcessingDisposition:
        return self.processing_disposition


class FileIndexRepository(Protocol):
    def find_by_path(
        self, storage_id: str, resource_library_id: str, path: str
    ) -> FileIndexRecord | None: ...

    def batch_upsert(self, records: Sequence[FileIndexRecord]) -> None: ...
    def list_by_resource_library(self, resource_library_id: str) -> Sequence[FileIndexRecord]: ...
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
    ) -> tuple[FileIndexRecord, ...]: ...

    def reconcile_missing(
        self,
        resource_library_id: str,
        scan_id: str,
        missing_at: datetime,
        *,
        protected_prefixes: Sequence[str] = (),
    ) -> int: ...

    def find_by_file_id(self, file_id: str, *, resource_library_id: str | None = None): ...

    def occurrence_history(self, file_id: str, *, limit: int = 32): ...

    def admit_reprocess(
        self,
        file_id: str,
        occurrence_id: str,
        fingerprint: str,
        *,
        actor: str,
        requested_at: datetime,
    ): ...

    def list_reprocess_requests(self, file_id: str, *, limit: int = 32): ...


def mark_missing(record: FileIndexRecord, timestamp: datetime) -> FileIndexRecord:
    return replace(
        record,
        scan_status=FileScanStatus.MISSING,
        change=FileChange.MISSING,
        missing_since=record.missing_since or timestamp,
        updated_at=timestamp,
    )
