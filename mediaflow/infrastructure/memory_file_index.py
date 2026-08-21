from __future__ import annotations

import threading
from collections.abc import Sequence
from datetime import datetime

from mediaflow.domain.file_index import FileIndexRecord, mark_missing


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
