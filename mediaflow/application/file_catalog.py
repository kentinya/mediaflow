from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from mediaflow.domain.file_catalog import FileReviewLink
from mediaflow.domain.file_index import FileIndexRecord, FileIndexRepository
from mediaflow.domain.media_evidence import PipelineEvidence, redact_pipeline_evidence
from mediaflow.domain.scanner import FileScanStatus
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    PersistentTaskRepository,
    redact_persistent_result,
)


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
    evidence: tuple[PipelineEvidence, ...] = ()
    items: tuple[FileDetailItem, ...] = ()
    results: tuple[PersistentResultRecord, ...] = ()
    actions: tuple[FileDetailAction, ...] = ()
    truncated: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class FileDetailItem:
    task_id: str
    item_id: str
    status: str
    stage: str
    updated_at: datetime
    source_storage_id: str
    resource_library_id: str
    source_path: str
    checkpoint: dict[str, object] | None = None
    source_occurrence_id: str | None = None
    source_fingerprint: str | None = None
    source_fingerprint_state: str = "unverified"


@dataclass(frozen=True)
class FileDetailAction:
    action_id: str
    label: str
    confirmation_required: bool
    required_authority: str
    resolution_surface: str | None
    admissible: bool
    task_id: str
    item_id: str


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
        checkpoint_service=None,
    ) -> None:
        self._repository = repository
        self._resource_library_ids = resource_library_ids
        self._storage_ids = storage_ids
        self._task_repository = task_repository
        self._checkpoint_service = checkpoint_service

    def attach_checkpoint_service(self, checkpoint_service) -> None:
        self._checkpoint_service = checkpoint_service

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
        latest_result = None
        if self._task_repository is not None:
            latest_value = self._task_repository.get_latest_result_for_source(
                record.storage_id, record.path
            )
            if latest_value is not None:
                latest_result = redact_persistent_result(latest_value, redact_identity=True)
        related_reviews: tuple[FileReviewLink, ...] = ()
        evidence: tuple[PipelineEvidence, ...] = ()
        items: tuple[FileDetailItem, ...] = ()
        results: tuple[PersistentResultRecord, ...] = ()
        truncated: dict[str, bool] = {}
        if self._task_repository is not None:
            list_reviews = getattr(self._task_repository, "list_file_review_links", None)
            if callable(list_reviews):
                review_values = list_reviews(record.storage_id, record.path, limit=101)
                truncated["reviews"] = len(review_values) > 100
                related_reviews = tuple(review_values[:100])
            list_evidence = getattr(self._task_repository, "list_evidence_for_source", None)
            if callable(list_evidence):
                evidence_values = list_evidence(record.storage_id, record.path, limit=33)
                truncated["evidence"] = len(evidence_values) > 32
                evidence = tuple(redact_pipeline_evidence(value) for value in evidence_values[:32])
            list_items = getattr(self._task_repository, "list_task_items_for_source", None)
            if callable(list_items):
                item_values = list_items(record.storage_id, record.path, limit=33)
                truncated["items"] = len(item_values) > 32
                items = tuple(
                    self._detail_item(value, record.storage_id, record.path)
                    for value in item_values[:32]
                )
            list_results = getattr(self._task_repository, "list_results_for_source", None)
            if callable(list_results):
                result_values = list_results(record.storage_id, record.path, limit=33)
                truncated["results"] = len(result_values) > 32
                results = tuple(
                    redact_persistent_result(value, redact_identity=True)
                    for value in result_values[:32]
                )
        actions = self._current_actions(items, record)
        return FileCatalogDetail(
            record,
            latest_result,
            related_reviews,
            evidence,
            items,
            results,
            actions,
            truncated,
        )

    def resolve_by_source(
        self,
        storage_id: str,
        path: str,
        *,
        resource_library_id: str | None = None,
    ) -> tuple[FileIndexRecord | None, str | None]:
        if not isinstance(storage_id, str) or not storage_id:
            raise ValueError("source Storage ID is required")
        if not isinstance(path, str) or not path:
            raise ValueError("source Storage-relative path is required")
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
        matches: list[FileIndexRecord] = []
        find = getattr(self._repository, "find_by_path", None)
        for library_id in library_ids:
            record = find(storage_id, library_id, path) if callable(find) else None
            if record is not None:
                matches.append(record)
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            return None, "ambiguous"
        return None, "missing"

    def _detail_item(self, item, storage_id: str, path: str) -> FileDetailItem:
        checkpoint = None
        checkpoint_service = self._checkpoint_service
        if checkpoint_service is None and self._task_repository is not None:
            from mediaflow.application.processing_checkpoint import ProcessingCheckpointService

            checkpoint_service = ProcessingCheckpointService(self._task_repository)
        if checkpoint_service is not None:
            try:
                # File/Media detail needs the same bounded checkpoint projection as the
                # TaskItem surface: audits, effects, blocker and permitted actions must
                # remain attributable after reload rather than being reduced to a status
                # summary.
                checkpoint = checkpoint_service.get(item.item_id, task_id=item.task_id).document()
            except (LookupError, ValueError):
                checkpoint = None
        return FileDetailItem(
            item.task_id,
            item.item_id,
            getattr(item.status, "value", str(item.status)),
            getattr(item, "stage", "unknown"),
            item.updated_at,
            storage_id,
            item.resource_library_id,
            path,
            checkpoint,
            getattr(item, "source_occurrence_id", None),
            getattr(item, "source_fingerprint", None),
            getattr(item, "source_fingerprint_state", "unverified"),
        )

    def _current_actions(
        self,
        items: tuple[FileDetailItem, ...],
        record: FileIndexRecord | None = None,
    ) -> tuple[FileDetailAction, ...]:
        if not items:
            return ()
        if record is not None and record.occurrence_id is not None:
            current_items = tuple(
                item
                for item in items
                if item.source_occurrence_id == record.occurrence_id
                and item.source_fingerprint_state == "verified"
                and item.source_fingerprint == record.fingerprint
            )
            # A legacy item has no occurrence link and must not become a current action for a
            # verified replacement.  Legacy FileIndex rows retain their old behavior below.
            if record.occurrence_state.value != "legacy":
                items = current_items
            elif current_items:
                items = current_items
        if not items:
            return ()
        actionable = [
            item
            for item in items
            if isinstance(item.checkpoint, dict)
            and isinstance(item.checkpoint.get("permitted_action_ids"), list)
            and item.checkpoint["permitted_action_ids"]
        ]
        latest = max(
            actionable or items,
            key=lambda item: (item.updated_at, item.item_id),
        )
        checkpoint = latest.checkpoint if isinstance(latest.checkpoint, dict) else None
        if checkpoint is None or not isinstance(checkpoint.get("permitted_action_ids"), list):
            return ()
        checkpoint_service = self._checkpoint_service
        if checkpoint_service is None and self._task_repository is not None:
            from mediaflow.application.processing_checkpoint import ProcessingCheckpointService

            checkpoint_service = ProcessingCheckpointService(self._task_repository)
        if checkpoint_service is None:
            return ()
        try:
            full = checkpoint_service.get(latest.item_id, task_id=latest.task_id)
        except (LookupError, ValueError):
            return ()
        actions: list[FileDetailAction] = []
        for action in full.actions:
            actions.append(
                FileDetailAction(
                    action.action_id,
                    action.label,
                    action.confirmation_required,
                    action.required_authority,
                    action.resolution_surface,
                    action.admissible,
                    latest.task_id,
                    latest.item_id,
                )
            )
        return tuple(actions)

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
