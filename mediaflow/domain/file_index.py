from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

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

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.storage_id, self.resource_library_id, self.path


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


def mark_missing(record: FileIndexRecord, timestamp: datetime) -> FileIndexRecord:
    return replace(
        record,
        scan_status=FileScanStatus.MISSING,
        change=FileChange.MISSING,
        missing_since=record.missing_since or timestamp,
        updated_at=timestamp,
    )
