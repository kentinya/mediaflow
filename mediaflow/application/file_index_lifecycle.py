"""Operator-facing FileIndex lifecycle projection and bounded Reprocess admission."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from mediaflow.application.file_catalog import (
    FileCatalogDetail,
    FileCatalogFilter,
)
from mediaflow.domain.file_index import FileIndexRecord
from mediaflow.domain.file_lifecycle import (
    FileIndexOccurrence,
    OccurrenceState,
    ProcessingDisposition,
    ReprocessRequest,
)
from mediaflow.domain.task_persistence import (
    PersistentResultRecord,
    redact_persistent_result,
)


@dataclass(frozen=True)
class FileIndexProjection:
    """Single read projection joining discovery, occurrence, processing and history."""

    detail: FileCatalogDetail
    occurrence_history: tuple[FileIndexOccurrence, ...]
    current_result: PersistentResultRecord | None
    result_relevance: tuple[tuple[PersistentResultRecord, str], ...]
    reprocess_eligible: bool
    reprocess_reason: str
    reprocess_requests: tuple[ReprocessRequest, ...] = ()

    @property
    def record(self) -> FileIndexRecord:
        return self.detail.record

    def eligibility_document(self) -> dict[str, object]:
        return {
            "eligible": self.reprocess_eligible,
            "reason": self.reprocess_reason,
            "required": {
                "occurrenceId": self.record.occurrence_id,
                "fingerprint": self.record.fingerprint,
            },
        }


class FileIndexLifecycleService:
    """Shared application behavior for FileIndex reads and Reprocess admission."""

    def __init__(self, file_catalog, file_index=None, task_repository=None, *, clock=None) -> None:
        self._catalog = file_catalog
        self._file_index = file_index or getattr(file_catalog, "_repository", None)
        self._task_repository = task_repository or getattr(file_catalog, "_task_repository", None)
        self._clock = clock or (lambda: datetime.now(UTC))

    def list(self, value: FileCatalogFilter) -> tuple[FileIndexRecord, ...]:
        return self._catalog.list(value)

    def detail(
        self, file_id: str, *, resource_library_id: str | None = None
    ) -> FileIndexProjection:
        detail = self._catalog.detail(file_id, resource_library_id=resource_library_id)
        history = self._history(detail.record)
        relevance = tuple(
            (result, self._result_relevance(detail.record, result)) for result in detail.results
        )
        current_result = next(
            (result for result, relation in relevance if relation == "current"),
            None,
        )
        if current_result is None:
            current_result = self._current_result(detail.record)
        if current_result is None and detail.record.occurrence_state is OccurrenceState.LEGACY:
            # Pre-lifecycle records remain readable for compatibility, but the relation is
            # explicitly unverified and never drives processing disposition or Reprocess.
            current_result = detail.latest_result
        eligible, reason = self._reprocess_eligibility(detail.record, current_result)
        return FileIndexProjection(
            detail,
            history,
            current_result,
            relevance,
            eligible,
            reason,
            self._requests(detail.record),
        )

    def project(self, detail: FileCatalogDetail) -> FileIndexProjection:
        history = self._history(detail.record)
        relevance = tuple(
            (result, self._result_relevance(detail.record, result)) for result in detail.results
        )
        current_result = next(
            (result for result, relation in relevance if relation == "current"),
            None,
        )
        if current_result is None:
            current_result = self._current_result(detail.record)
        if current_result is None and detail.record.occurrence_state is OccurrenceState.LEGACY:
            current_result = detail.latest_result
        eligible, reason = self._reprocess_eligibility(detail.record, current_result)
        return FileIndexProjection(
            detail,
            history,
            current_result,
            relevance,
            eligible,
            reason,
            self._requests(detail.record),
        )

    def admit_reprocess(
        self,
        file_id: str,
        occurrence_id: str,
        fingerprint: str,
        *,
        actor: str,
    ) -> ReprocessRequest:
        if self._file_index is None:
            raise ValueError("FileIndex lifecycle repository is unavailable")
        admit = getattr(self._file_index, "admit_reprocess", None)
        if not callable(admit):
            raise ValueError("FileIndex lifecycle admission is unavailable")
        return admit(
            file_id,
            occurrence_id,
            fingerprint,
            actor=actor,
            requested_at=self._clock(),
        )

    request_reprocess = admit_reprocess

    def _history(self, record: FileIndexRecord) -> tuple[FileIndexOccurrence, ...]:
        if record.occurrence_id is None or self._file_index is None:
            return ()
        history = getattr(self._file_index, "occurrence_history", None)
        return tuple(history(record.file_id, limit=32)) if callable(history) else ()

    def _requests(self, record: FileIndexRecord) -> tuple[ReprocessRequest, ...]:
        if self._file_index is None:
            return ()
        list_requests = getattr(self._file_index, "list_reprocess_requests", None)
        return tuple(list_requests(record.file_id, limit=32)) if callable(list_requests) else ()

    def _current_result(self, record: FileIndexRecord) -> PersistentResultRecord | None:
        if (
            self._task_repository is None
            or record.occurrence_id is None
            or record.fingerprint is None
        ):
            return None
        getter = getattr(self._task_repository, "get_latest_result_for_occurrence", None)
        if not callable(getter):
            return None
        value = getter(record.storage_id, record.path, record.occurrence_id, record.fingerprint)
        if value is not None and _value_state(value.source_fingerprint_state) != "verified":
            return None
        return redact_persistent_result(value, redact_identity=True) if value is not None else None

    @staticmethod
    def _result_relevance(record: FileIndexRecord, result: PersistentResultRecord) -> str:
        if (
            record.occurrence_state is not OccurrenceState.VERIFIED
            or record.occurrence_id is None
            or result.source_occurrence_id is None
            or _value_state(result.source_fingerprint_state) != "verified"
        ):
            return "unverified_legacy"
        if result.source_occurrence_id != record.occurrence_id:
            return "historical_different_occurrence"
        if result.source_fingerprint != record.fingerprint:
            return "historical_fingerprint_mismatch"
        return "current"

    @staticmethod
    def _reprocess_eligibility(
        record: FileIndexRecord, current_result: PersistentResultRecord | None
    ) -> tuple[bool, str]:
        if record.scan_status.value != "ready":
            return False, "the current source is not stable and ready"
        if record.occurrence_state is not OccurrenceState.VERIFIED or not record.fingerprint:
            return False, "the current source occurrence is unverified"
        if current_result is None:
            return False, "no current processing Result suppresses duplicate work"
        if record.processing_disposition in {
            ProcessingDisposition.UNKNOWN,
            ProcessingDisposition.UNVERIFIED,
            ProcessingDisposition.REPROCESS_REQUESTED,
        }:
            return False, "the current processing disposition is not eligible for Reprocess"
        if record.processing_retry_safety != "safe":
            return False, "the current Result effect is not verified safe to repeat"
        return True, "explicit Reprocess is available for this current occurrence"


# Short alias for integrations that use the FileIndex name rather than the lifecycle name.
FileIndexService = FileIndexLifecycleService


def _value_state(value: object) -> str:
    return str(getattr(value, "value", value) or "unverified").lower()
