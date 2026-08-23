from __future__ import annotations

import threading
from collections.abc import Sequence
from datetime import datetime

from mediaflow.domain.file_index import FileIndexRecord, mark_missing
from mediaflow.domain.scanner import FileScanStatus


class InMemoryFileIndexRepository:
    """Thread-safe test/bootstrap repository; production databases can implement the same port."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], FileIndexRecord] = {}
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
                self._records[record.identity] = record

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
