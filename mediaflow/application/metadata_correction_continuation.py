from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from mediaflow.domain.automation import AutomationCommand, AutomationJob, AutomationJobStatus
from mediaflow.domain.metadata_correction import (
    MetadataCorrectionContinuation,
    MetadataCorrectionContinuationStatus,
    MetadataCorrectionReview,
    MetadataCorrectionSelection,
    MetadataCorrectionStatus,
)
from mediaflow.domain.task_persistence import PersistentTaskItem, TaskItemStatus

if TYPE_CHECKING:
    from mediaflow.application.manual_source_validation import (
        ManualSourceValidator,
        PersistedSourceValidation,
    )

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}")
_ACTIVE_STATUSES = {
    MetadataCorrectionContinuationStatus.QUEUED,
    MetadataCorrectionContinuationStatus.RUNNING,
}
_RECOVERY = (
    "inspect the linked Task/TaskItem, repair the stated input or runtime condition, "
    "then continue only this correction when eligible"
)


class MetadataCorrectionContinuationConflict(RuntimeError):
    def __init__(self, message: str, continuation: MetadataCorrectionContinuation | None) -> None:
        super().__init__(message)
        self.continuation = continuation


@dataclass(frozen=True)
class MetadataCorrectionContinuationSubmission:
    continuation: MetadataCorrectionContinuation
    job: AutomationJob
    created: bool


@dataclass(frozen=True)
class PreparedMetadataCorrectionContinuation:
    continuation: MetadataCorrectionContinuation
    review: MetadataCorrectionReview
    source_item: PersistentTaskItem
    selection: MetadataCorrectionSelection
    #: The live, verified re-observation of the exact persisted source, or
    #: ``None`` when this Worker was assembled without a live source boundary.
    live_source: PersistedSourceValidation | None = None

    @property
    def source_observed_at(self):
        """The durable instant this work first observed the exact source.

        A continuation measures the configured stable-size interval from this
        instant; a trusted fingerprint alone never proves elapsed stability.
        """

        return self.source_item.source_observed_at


@dataclass(frozen=True)
class MetadataCorrectionContinuationContext:
    review: MetadataCorrectionReview
    source_item: PersistentTaskItem
    configuration_snapshot_id: str
    configuration_snapshot_digest: str
    correction_version: str
    current: MetadataCorrectionContinuation | None


class FileMetadataCorrectionContinuationService:
    """Shared API/Web admission for exactly one pinned Metadata correction continuation."""

    MAX_ACTOR = 200

    def __init__(
        self,
        repository,
        *,
        snapshot_validator: Callable[[str, str], None] | None = None,
    ) -> None:
        self._repository = repository
        self._snapshot_validator = snapshot_validator

    def context(
        self, task_id: str, item_id: str, review_id: str
    ) -> MetadataCorrectionContinuationContext:
        """Resolve exactly one reviewed source from its own durable Task linkage.

        The durable (Task, TaskItem, review) triple *is* the source authority: it
        carries the exact Storage/library/path and the pinned snapshot, so no
        file catalog lookup is needed and no current-scope read can silently
        substitute a different source.
        """

        self._identifier(task_id, "Task ID")
        self._identifier(item_id, "Task item ID")
        self._identifier(review_id, "Metadata correction ID")
        review = self._repository.get_metadata_correction(review_id)
        if review is None:
            raise ValueError(f"metadata correction {review_id!r} was not found")
        if review.task_id != task_id or review.item_id != item_id:
            raise ValueError("Metadata correction is not linked to this Task item")
        task = self._repository.get_task(review.task_id)
        item = self._repository.get_item(review.item_id)
        if task is None or item is None or item.task_id != task.task_id:
            raise ValueError("Metadata correction source Task linkage is unavailable")
        if item.storage_id != review.source_storage_id or item.source_path != review.source_path:
            raise ValueError("Metadata correction source TaskItem linkage is unavailable")
        if review.status is not MetadataCorrectionStatus.RESOLVED:
            raise ValueError("Metadata correction is unresolved or superseded")
        if review.corrected_media_type is None:
            raise ValueError("Metadata correction has no immutable resolved selection")
        if item.status is not TaskItemStatus.PENDING:
            raise ValueError("source TaskItem is not eligible for Metadata continuation")
        if not task.configuration_snapshot_id or not task.configuration_snapshot_digest:
            raise ValueError("source Task has no immutable configuration snapshot pin")
        return MetadataCorrectionContinuationContext(
            review,
            item,
            task.configuration_snapshot_id,
            task.configuration_snapshot_digest,
            self.correction_version(review),
            self._repository.get_metadata_correction_continuation_for_review(review.review_id),
        )

    def submit(
        self,
        task_id: str,
        item_id: str,
        review_id: str,
        *,
        expected_correction_version: str,
        actor: str,
        maximum_active_jobs: int,
    ) -> MetadataCorrectionContinuationSubmission:
        normalized_actor = self._text(actor, self.MAX_ACTOR)
        if not normalized_actor:
            raise ValueError("continuation actor is required")
        self._version(expected_correction_version)
        if (
            isinstance(maximum_active_jobs, bool)
            or not isinstance(maximum_active_jobs, int)
            or not 1 <= maximum_active_jobs <= 10_000
        ):
            raise ValueError("maximum active Jobs must be between 1 and 10000")
        context = self.context(task_id, item_id, review_id)
        if context.correction_version != expected_correction_version:
            raise MetadataCorrectionContinuationConflict(
                "Metadata correction identity is stale; refresh the File detail",
                context.current,
            )
        if context.current and context.current.status in _ACTIVE_STATUSES | {
            MetadataCorrectionContinuationStatus.COMPLETED
        }:
            raise MetadataCorrectionContinuationConflict(
                "this Metadata correction already has a durable continuation",
                context.current,
            )
        if self._snapshot_validator is not None:
            self._snapshot_validator(
                context.configuration_snapshot_id,
                context.configuration_snapshot_digest,
            )
        now = datetime.now(UTC)
        job = AutomationJob(
            str(uuid4()),
            AutomationCommand.FILE_METADATA_CORRECTION,
            AutomationJobStatus.PENDING,
            now,
            now,
            limit=1,
            execute_authorized=False,
            configuration_snapshot_id=context.configuration_snapshot_id,
            configuration_snapshot_digest=context.configuration_snapshot_digest,
        )
        continuation = MetadataCorrectionContinuation(
            str(uuid4()),
            item_id,
            context.review.review_id,
            context.review.task_id,
            context.source_item.item_id,
            context.configuration_snapshot_id,
            context.configuration_snapshot_digest,
            context.correction_version,
            MetadataCorrectionContinuationStatus.QUEUED,
            now,
            now,
            normalized_actor,
            job.job_id,
        )
        admitted, created = self._repository.admit_metadata_correction_continuation(
            job, continuation, maximum_active_jobs=maximum_active_jobs
        )
        if not created:
            raise MetadataCorrectionContinuationConflict(
                "this Metadata correction already has a durable continuation",
                admitted,
            )
        return MetadataCorrectionContinuationSubmission(admitted, job, True)

    @staticmethod
    def correction_version(review: MetadataCorrectionReview) -> str:
        if review.decided_at is None:
            raise ValueError("resolved Metadata correction has no decision identity")
        identity = {
            "reviewId": review.review_id,
            "correctedQuery": review.corrected_query,
            "correctedYear": review.corrected_year,
            "correctedMediaType": review.corrected_media_type,
            "directProviderId": review.direct_provider_id,
            "decidedAt": review.decided_at.isoformat(),
        }
        encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _identifier(value: str, label: str) -> None:
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise ValueError(f"{label} is invalid")

    @staticmethod
    def _version(value: str) -> None:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("expected Metadata correction identity must be a SHA-256 digest")

    @staticmethod
    def _text(value: str | None, limit: int) -> str | None:
        normalized = " ".join(value.split())[:limit] if isinstance(value, str) else ""
        return normalized or None


class MetadataCorrectionContinuationWorkerService:
    """Durable claim/outcome boundary around the existing one-file production pipeline."""

    def __init__(
        self, repository, *, source_validator: ManualSourceValidator | None = None
    ) -> None:
        self._repository = repository
        self._source_validator = source_validator

    def prepare(self, job_id: str) -> PreparedMetadataCorrectionContinuation:
        self._job_identifier(job_id)
        job = self._repository.get_job(job_id)
        if job is None:
            raise LookupError(f"automation Job {job_id!r} was not found")
        if job.command is not AutomationCommand.FILE_METADATA_CORRECTION:
            raise ValueError("automation Job is not a Metadata correction continuation")
        if job.status not in {AutomationJobStatus.PENDING, AutomationJobStatus.RUNNING}:
            raise ValueError("metadata correction continuation Job is not active")
        if job.cancellation_requested:
            raise ValueError("metadata correction continuation Job cancellation was requested")
        if job.execute_authorized:
            raise ValueError("metadata correction continuation Job cannot authorize execution")
        if job.limit != 1 or job.schedule_id is not None or job.task_id is not None:
            raise ValueError("metadata correction continuation Job identity is invalid")
        if not job.configuration_snapshot_id or not job.configuration_snapshot_digest:
            raise ValueError("metadata correction continuation Job has no snapshot pin")
        continuation = self._repository.get_metadata_correction_continuation_for_job(job_id)
        if continuation is None:
            raise LookupError(f"metadata correction continuation for Job {job_id!r} was not found")
        if continuation.status not in _ACTIVE_STATUSES:
            raise ValueError("metadata correction continuation is not active")
        review = self._repository.get_metadata_correction(continuation.review_id)
        task = self._repository.get_task(continuation.source_task_id)
        item = self._repository.get_item(continuation.source_item_id)
        if review is None or task is None or item is None:
            raise ValueError("metadata correction continuation linkage is unavailable")
        version = FileMetadataCorrectionContinuationService.correction_version(review)
        if version != continuation.correction_version:
            raise ValueError("metadata correction continuation identity is stale")
        if (
            review.status is not MetadataCorrectionStatus.RESOLVED
            or review.task_id != task.task_id
            or review.item_id != item.item_id
            or item.task_id != task.task_id
            or item.status is not TaskItemStatus.PENDING
        ):
            raise ValueError("metadata correction continuation eligibility changed")
        if (
            task.configuration_snapshot_id != continuation.configuration_snapshot_id
            or task.configuration_snapshot_digest != continuation.configuration_snapshot_digest
        ):
            raise ValueError("source Task configuration snapshot changed")
        if (
            job.configuration_snapshot_id != continuation.configuration_snapshot_id
            or job.configuration_snapshot_digest != continuation.configuration_snapshot_digest
        ):
            raise ValueError("continuation Job configuration snapshot changed")
        live_source = self._validate_live_source(item, continuation)
        return PreparedMetadataCorrectionContinuation(
            continuation,
            review,
            item,
            MetadataCorrectionSelection(
                review.recognition_type,
                review.metadata_policy_id,
                review.provider_id,
                review.corrected_query,
                review.corrected_year,
                review.corrected_media_type or "",
                review.direct_provider_id,
            ),
            live_source,
        )

    def _validate_live_source(self, item, continuation) -> PersistedSourceValidation | None:
        """Prove the exact persisted source still exists under its pinned Active pin.

        The retired index preflight only checked that a catalog row still carried
        the same File identity.  With the index gone, the same shared live-Storage
        boundary used by manual intents must re-observe the exact source before
        any saved correction or Provider analysis is consumed, so a replaced or
        missing file is refused instead of analyzed under a stale identity.
        """

        if self._source_validator is None:
            return None
        from mediaflow.application.manual_source_validation import PersistedSourceEvidence

        return self._source_validator.validate_persisted_source(
            PersistedSourceEvidence(
                storage_id=item.storage_id,
                resource_library_id=item.resource_library_id,
                path=item.source_path,
                occurrence_id=item.source_occurrence_id,
                fingerprint=item.source_fingerprint,
                fingerprint_state=item.source_fingerprint_state,
            ),
            snapshot_id=continuation.configuration_snapshot_id,
            snapshot_digest=continuation.configuration_snapshot_digest,
        )

    def started(self, job_id: str) -> MetadataCorrectionContinuation:
        return self._repository.mark_metadata_correction_continuation_running(job_id)

    def cancelled(self, job_id: str) -> MetadataCorrectionContinuation:
        return self._repository.cancel_metadata_correction_continuation(job_id)

    def finish(self, job_id: str, task_id: str) -> MetadataCorrectionContinuation:
        task = self._repository.get_task(task_id)
        if task is None:
            return self._repository.complete_metadata_correction_continuation(
                job_id,
                new_task_id=task_id,
                success=False,
                error="continuation Task was not persisted",
                recovery=_RECOVERY,
            )
        items = self._repository.list_items(task_id)
        results = self._repository.list_results(task_id)
        result = (
            next(
                (value for value in reversed(results) if value.item_id == items[0].item_id),
                None,
            )
            if items
            else None
        )
        successful = (
            len(items) == 1
            and items[0].status is TaskItemStatus.DRY_RUN
            and result is not None
            and result.status == TaskItemStatus.DRY_RUN.value
        )
        result_id = result.result_id if result is not None else None
        if successful:
            return self._repository.complete_metadata_correction_continuation(
                job_id,
                new_task_id=task_id,
                new_result_id=result_id,
                success=True,
            )
        if items and items[0].status is TaskItemStatus.WAITING_METADATA_CORRECTION:
            error = "corrected metadata identity was not found"
            recovery = (
                "inspect the new Metadata correction review, resolve it, then continue only "
                "that new item"
            )
        elif items and items[0].error:
            error = "single-item DryRun analysis failed"
            recovery = _RECOVERY
        else:
            error = "single-item DryRun did not produce a completed Preview/Result"
            recovery = _RECOVERY
        return self._repository.complete_metadata_correction_continuation(
            job_id,
            new_task_id=task_id,
            new_result_id=result_id,
            success=False,
            error=error,
            recovery=recovery,
        )

    def failed(
        self,
        job_id: str,
        *,
        task_id: str | None = None,
        snapshot_unavailable: bool = False,
        queued: bool = False,
        preflight: bool = False,
        error: str | None = None,
        recovery: str | None = None,
    ) -> None:
        error = error or (
            "saved configuration snapshot is unavailable"
            if snapshot_unavailable
            else "continuation linkage or eligibility validation failed before pipeline"
            if preflight
            else "continuation failed before Task completion"
        )
        recovery = recovery or (
            "restore the saved published revision, or create a new correction under the current "
            "Active configuration"
            if snapshot_unavailable
            else "inspect the linked File/Task/TaskItem, repair the stale condition, then retry "
            "only this correction"
            if preflight
            else _RECOVERY
        )
        try:
            if queued:
                self._repository.fail_queued_metadata_correction_continuation(
                    job_id,
                    error=error,
                    recovery=recovery,
                )
            else:
                self._repository.complete_metadata_correction_continuation(
                    job_id,
                    new_task_id=task_id,
                    success=False,
                    error=error,
                    recovery=recovery,
                )
        except (LookupError, ValueError):
            pass

    @staticmethod
    def _job_identifier(value: str) -> None:
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise ValueError("continuation Job ID is invalid")
