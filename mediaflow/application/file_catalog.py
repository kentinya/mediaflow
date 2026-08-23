from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from mediaflow.domain.file_catalog import FileReviewLink
from mediaflow.domain.file_index import FileIndexRecord, FileIndexRepository
from mediaflow.domain.scanner import FileScanStatus
from mediaflow.domain.task_persistence import PersistentResultRecord, PersistentTaskRepository


@dataclass(frozen=True)
class FileCatalogFilter:
    resource_library_id: str | None = None
    storage_id: str | None = None
    scan_status: FileScanStatus | None = None
    query: str | None = None
    limit: int = 100
    after: tuple[datetime, str] | None = None
    before: tuple[datetime, str] | None = None
    recognition_type: str | None = None
    provider: str | None = None
    provider_id: str | None = None
    title: str | None = None
    task_id: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class FileCatalogDetail:
    record: FileIndexRecord
    latest_result: PersistentResultRecord | None
    related_reviews: tuple[FileReviewLink, ...] = ()


@dataclass(frozen=True)
class FileCatalogStats:
    total: int
    by_status: dict[FileScanStatus, int]


class FileCatalogService:
    MAX_RESULTS = 1000

    def __init__(
        self,
        repository: FileIndexRepository,
        resource_library_ids: tuple[str, ...],
        storage_ids: tuple[str, ...],
        task_repository: PersistentTaskRepository | None = None,
    ) -> None:
        self._repository = repository
        self._resource_library_ids = resource_library_ids
        self._storage_ids = storage_ids
        self._task_repository = task_repository

    def list(self, value: FileCatalogFilter) -> tuple[FileIndexRecord, ...]:
        self._validate(value)
        library_ids = (
            (value.resource_library_id,)
            if value.resource_library_id is not None
            else self._resource_library_ids
        )
        if self._has_derived_filter(value):
            if self._task_repository is None:
                raise ValueError("file catalog derived filters require a Task repository")
            if hasattr(self._repository, "list_enriched_catalog"):
                enriched = self._repository.list_enriched_catalog(
                    library_ids,
                    storage_id=value.storage_id,
                    scan_status=value.scan_status,
                    query=value.query,
                    limit=value.limit,
                    after=value.after,
                    before=value.before,
                    recognition_type=value.recognition_type,
                    provider=value.provider,
                    provider_id=value.provider_id,
                    title=value.title,
                    task_id=value.task_id,
                    year=value.year,
                )
                return tuple(item.file for item in enriched)
        records = list(
            self._repository.list_catalog(
                library_ids,
                storage_id=value.storage_id,
                scan_status=value.scan_status,
                query=value.query,
                limit=value.limit,
                after=value.after,
                before=value.before,
            )
        )
        if self._has_derived_filter(value):
            records = [
                record
                for record in records
                if self._matches_derived(
                    self._task_repository.get_latest_result_for_source(
                        record.storage_id, record.path
                    ),
                    value,
                )
            ]
        return tuple(records)

    def show(self, file_id: str, *, resource_library_id: str | None = None) -> FileIndexRecord:
        library_ids = (
            (resource_library_id,)
            if resource_library_id is not None
            else self._resource_library_ids
        )
        if (
            resource_library_id is not None
            and resource_library_id not in self._resource_library_ids
        ):
            raise ValueError(f"unknown ResourceLibrary {resource_library_id!r}")
        for library_id in library_ids:
            for record in self._repository.list_by_resource_library(library_id):
                if record.file_id == file_id:
                    return record
        raise LookupError(f"FileIndex record {file_id!r} was not found")

    def detail(self, file_id: str, *, resource_library_id: str | None = None) -> FileCatalogDetail:
        record = self.show(file_id, resource_library_id=resource_library_id)
        latest_result = (
            self._task_repository.get_latest_result_for_source(record.storage_id, record.path)
            if self._task_repository is not None
            else None
        )
        related_reviews = (
            self._task_repository.list_file_review_links(record.storage_id, record.path)
            if self._task_repository is not None
            and hasattr(self._task_repository, "list_file_review_links")
            else ()
        )
        return FileCatalogDetail(record, latest_result, related_reviews)

    def stats(
        self,
        *,
        resource_library_id: str | None = None,
        storage_id: str | None = None,
    ) -> FileCatalogStats:
        if (
            resource_library_id is not None
            and resource_library_id not in self._resource_library_ids
        ):
            raise ValueError(f"unknown ResourceLibrary {resource_library_id!r}")
        if storage_id is not None and storage_id not in self._storage_ids:
            raise ValueError(f"unknown Storage {storage_id!r}")
        library_ids = (
            (resource_library_id,)
            if resource_library_id is not None
            else self._resource_library_ids
        )
        counts: dict[FileScanStatus, int] = {}
        total = 0
        for library_id in library_ids:
            for record in self._repository.list_by_resource_library(library_id):
                if storage_id is not None and record.storage_id != storage_id:
                    continue
                total += 1
                counts[record.scan_status] = counts.get(record.scan_status, 0) + 1
        return FileCatalogStats(total, counts)

    def _validate(self, value: FileCatalogFilter) -> None:
        if (
            value.resource_library_id is not None
            and value.resource_library_id not in self._resource_library_ids
        ):
            raise ValueError(f"unknown ResourceLibrary {value.resource_library_id!r}")
        if value.storage_id is not None and value.storage_id not in self._storage_ids:
            raise ValueError(f"unknown Storage {value.storage_id!r}")
        if value.after is not None and value.before is not None:
            raise ValueError("file catalog after and before are mutually exclusive")
        for cursor in (value.after, value.before):
            if cursor is None:
                continue
            if not isinstance(cursor[1], str) or not cursor[1]:
                raise ValueError("file catalog cursor file ID is required")
        if (
            isinstance(value.limit, bool)
            or not isinstance(value.limit, int)
            or not 1 <= value.limit <= self.MAX_RESULTS
        ):
            raise ValueError(f"file catalog limit must be between 1 and {self.MAX_RESULTS}")
        if value.year is not None and (
            isinstance(value.year, bool)
            or not isinstance(value.year, int)
            or not 1870 <= value.year <= 2100
        ):
            raise ValueError("file catalog year must be between 1870 and 2100")

    @staticmethod
    def _has_derived_filter(value: FileCatalogFilter) -> bool:
        return any(
            (
                value.recognition_type,
                value.provider,
                value.provider_id,
                value.title,
                value.task_id,
                value.year is not None,
            )
        )

    @staticmethod
    def _matches_derived(result: PersistentResultRecord | None, value: FileCatalogFilter) -> bool:
        if result is None:
            return False
        if value.recognition_type and result.recognition_type != value.recognition_type:
            return False
        if value.provider and result.provider != value.provider:
            return False
        if value.provider_id and result.provider_id != value.provider_id:
            return False
        if value.title and value.title.lower() not in (result.title or "").lower():
            return False
        if value.task_id and result.task_id != value.task_id:
            return False
        if value.year is not None:
            title_year = FileCatalogService._title_year(result.title)
            if title_year is None or title_year != value.year:
                return False
        return True

    @staticmethod
    def _title_year(title: str | None) -> int | None:
        if not title:
            return None
        match = re.search(r"(?<!\d)(18\d{2}|19\d{2}|20\d{2})(?!\d)", title)
        return int(match.group(1)) if match else None
