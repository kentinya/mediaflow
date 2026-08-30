"""Application boundary for analysis-only recovery continuations.

The submit service turns one active admitted request into a durable, bounded
continuation (queued Job + continuation row) and the worker service validates
and drives that continuation to a terminal state, resolving the parent request
so the item can be decided again.  Neither service ever executes media work or
touches Storage/Provider boundaries.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from mediaflow.application.processing_checkpoint import ProcessingCheckpointService
from mediaflow.domain.automation import AutomationCommand, AutomationJob, AutomationJobStatus
from mediaflow.domain.configuration_management import RuntimeSnapshotUnavailable
from mediaflow.domain.processing_checkpoint import EffectCertainty
from mediaflow.domain.recovery import RecoveryRequest
from mediaflow.domain.recovery_continuation import (
    RecoveryContinuation,
    RecoveryContinuationError,
    RecoveryContinuationReason,
    RecoveryContinuationStatus,
)
from mediaflow.domain.task_persistence import PersistentTaskItem, TaskItemStatus

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}")
_ACTIVE_STATUSES = {
    RecoveryContinuationStatus.QUEUED,
    RecoveryContinuationStatus.RUNNING,
}
_CONTINUABLE_BOUNDARY = "source_scope_analysis"
_RECOVERY = (
    "inspect the linked Task/TaskItem, repair the stated input or runtime condition, "
    "then continue only this item when eligible"
)
_WAITING_STATUSES = {
    TaskItemStatus.WAITING_CONFIRM,
    TaskItemStatus.WAITING_RECOGNITION,
    TaskItemStatus.WAITING_METADATA,
    TaskItemStatus.WAITING_METADATA_CORRECTION,
    TaskItemStatus.WAITING_CLASSIFICATION,
}


@dataclass(frozen=True)
class RecoveryContinuationSubmission:
    continuation: RecoveryContinuation
    job: AutomationJob
    created: bool


@dataclass(frozen=True)
class PreparedRecoveryContinuation:
    continuation: RecoveryContinuation
    request: RecoveryRequest
    source_item: PersistentTaskItem


class RecoveryContinuationService:
    """Shared API/Web submission for exactly one admitted recovery request."""

    MAX_ACTOR = 200
    MAX_VERSION = 128

    def __init__(
        self,
        repository,
        *,
        snapshot_validator: Callable[[str, str], None] | None = None,
        checkpoint_service: ProcessingCheckpointService | None = None,
    ) -> None:
        self._repository = repository
        self._snapshot_validator = snapshot_validator
        self._checkpoint_service = checkpoint_service or ProcessingCheckpointService(
            repository, snapshot_validator=snapshot_validator
        )

    @property
    def repository(self):
        return self._repository

    @property
    def checkpoint_service(self) -> ProcessingCheckpointService:
        return self._checkpoint_service

    def submit(
        self,
        task_id: str,
        item_id: str,
        *,
        expected_checkpoint_version: str,
        actor: str,
        maximum_active_jobs: int,
    ) -> RecoveryContinuationSubmission:
        task_id = self._required_id(task_id, "Task ID")
        item_id = self._required_id(item_id, "TaskItem ID")
        expected = self._version(expected_checkpoint_version)
        actor = self._bounded_text(actor, self.MAX_ACTOR, "continuation actor")
        if actor is None:
            raise RecoveryContinuationError(
                RecoveryContinuationReason.INSUFFICIENT_AUTHORITY,
                "continuation actor is required",
            )
        if (
            isinstance(maximum_active_jobs, bool)
            or not isinstance(maximum_active_jobs, int)
            or not 1 <= maximum_active_jobs <= 10_000
        ):
            raise RecoveryContinuationError(
                RecoveryContinuationReason.INVALID_INPUT,
                "maximum active Jobs must be between 1 and 10000",
            )
        try:
            checkpoint = self._checkpoint_service.get(item_id)
        except LookupError:
            raise RecoveryContinuationError(
                RecoveryContinuationReason.UNKNOWN_ITEM,
                "TaskItem was not found",
            ) from None
        if checkpoint.task_id != task_id:
            raise RecoveryContinuationError(
                RecoveryContinuationReason.ITEM_TASK_MISMATCH,
                "TaskItem was not found in the specified Task",
            )
        request = checkpoint.active_recovery_request
        if request is None:
            if checkpoint.effect_certainty in {
                EffectCertainty.ATTEMPTED_UNVERIFIED,
                EffectCertainty.UNKNOWN,
            }:
                raise RecoveryContinuationError(
                    RecoveryContinuationReason.UNCERTAIN_EFFECTS,
                    "uncertain execution effects are never continued; investigate the checkpoint",
                    current_checkpoint_version=checkpoint.checkpoint_version,
                )
            raise RecoveryContinuationError(
                RecoveryContinuationReason.REQUEST_NOT_ACTIVE,
                "the admitted recovery request is not active",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )
        existing = self._repository.get_recovery_continuation_for_request(request.request_id)
        if existing is not None:
            raise RecoveryContinuationError(
                RecoveryContinuationReason.CONTINUATION_EXISTS,
                "this admitted recovery request already has a durable continuation",
                current_checkpoint_version=checkpoint.checkpoint_version,
                existing_continuation=existing,
            )
        if expected != checkpoint.checkpoint_version:
            raise RecoveryContinuationError(
                RecoveryContinuationReason.STALE_CHECKPOINT,
                "checkpoint version is stale; refresh before continuing recovery",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )
        if "continue" not in checkpoint.permitted_action_ids:
            raise RecoveryContinuationError(
                RecoveryContinuationReason.NO_CONTINUATION_BOUNDARY,
                "the current checkpoint does not support a safe continuation boundary",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )
        self._validate_snapshot(checkpoint)
        now = datetime.now(UTC)
        job = AutomationJob(
            str(uuid4()),
            AutomationCommand.RECOVERY_CONTINUATION,
            AutomationJobStatus.PENDING,
            now,
            now,
            limit=1,
            execute_authorized=False,
            configuration_snapshot_id=checkpoint.configuration.snapshot_id,
            configuration_snapshot_digest=checkpoint.configuration.snapshot_digest,
        )
        continuation = RecoveryContinuation(
            str(uuid4()),
            request.request_id,
            request.task_id,
            request.item_id,
            checkpoint.checkpoint_version,
            checkpoint.configuration.snapshot_id,
            checkpoint.configuration.snapshot_digest,
            _CONTINUABLE_BOUNDARY,
            RecoveryContinuationStatus.QUEUED,
            now,
            now,
            actor,
            job.job_id,
        )
        admitted, created = self._repository.admit_recovery_continuation(
            job,
            continuation,
            maximum_active_jobs=maximum_active_jobs,
            checkpoint_projector=self._checkpoint_service._project,
        )
        if not created:
            raise RecoveryContinuationError(
                RecoveryContinuationReason.CONTINUATION_EXISTS,
                "this admitted recovery request already has a durable continuation",
                existing_continuation=admitted,
            )
        return RecoveryContinuationSubmission(admitted, job, True)

    def _validate_snapshot(self, checkpoint) -> None:
        snapshot_id = checkpoint.configuration.snapshot_id
        snapshot_digest = checkpoint.configuration.snapshot_digest
        if not snapshot_id or not snapshot_digest:
            raise RecoveryContinuationError(
                RecoveryContinuationReason.SNAPSHOT_UNAVAILABLE,
                "the parent Task has no pinned configuration snapshot",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )
        if checkpoint.configuration.resolvable is False:
            raise RecoveryContinuationError(
                RecoveryContinuationReason.SNAPSHOT_UNAVAILABLE,
                "the pinned configuration snapshot is unavailable",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )
        if self._snapshot_validator is None:
            raise RecoveryContinuationError(
                RecoveryContinuationReason.SNAPSHOT_UNAVAILABLE,
                "the pinned configuration snapshot cannot be validated",
                current_checkpoint_version=checkpoint.checkpoint_version,
            )
        try:
            self._snapshot_validator(snapshot_id, snapshot_digest)
        except RuntimeSnapshotUnavailable as error:
            raise RecoveryContinuationError(
                RecoveryContinuationReason.SNAPSHOT_UNAVAILABLE,
                "the pinned configuration snapshot is unavailable",
                current_checkpoint_version=checkpoint.checkpoint_version,
            ) from error
        except Exception as error:
            raise RecoveryContinuationError(
                RecoveryContinuationReason.SNAPSHOT_UNAVAILABLE,
                "the pinned configuration snapshot cannot be validated",
                current_checkpoint_version=checkpoint.checkpoint_version,
            ) from error

    @staticmethod
    def _required_id(value: str, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise RecoveryContinuationError(
                RecoveryContinuationReason.INVALID_INPUT, f"{label} is required"
            )
        normalized = value.strip()
        if len(normalized) > 256:
            raise RecoveryContinuationError(
                RecoveryContinuationReason.INVALID_INPUT, f"{label} is too long"
            )
        return normalized

    @classmethod
    def _version(cls, value: str) -> str:
        normalized = cls._required_id(value, "checkpoint version")
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise RecoveryContinuationError(
                RecoveryContinuationReason.INVALID_VERSION,
                "checkpoint version is invalid",
            )
        return normalized

    @staticmethod
    def _bounded_text(value: str | None, limit: int, label: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise RecoveryContinuationError(
                RecoveryContinuationReason.INVALID_INPUT, f"{label} is invalid"
            )
        normalized = " ".join(value.split())
        if len(normalized) > limit:
            raise RecoveryContinuationError(
                RecoveryContinuationReason.INVALID_INPUT,
                f"{label} exceeds {limit} characters",
            )
        return normalized or None


class RecoveryContinuationWorkerService:
    """Durable claim/outcome boundary around the existing one-item pipeline."""

    def __init__(self, repository) -> None:
        self._repository = repository

    def prepare(self, job_id: str) -> PreparedRecoveryContinuation:
        self._job_identifier(job_id)
        job = self._repository.get_job(job_id)
        if job is None:
            raise LookupError(f"automation Job {job_id!r} was not found")
        if job.command is not AutomationCommand.RECOVERY_CONTINUATION:
            raise ValueError("automation Job is not a recovery continuation")
        if job.status not in {AutomationJobStatus.PENDING, AutomationJobStatus.RUNNING}:
            raise ValueError("recovery continuation Job is not active")
        if job.cancellation_requested:
            raise ValueError("recovery continuation Job cancellation was requested")
        if job.execute_authorized:
            raise ValueError("recovery continuation Job cannot authorize execution")
        if job.limit != 1 or job.schedule_id is not None or job.task_id is not None:
            raise ValueError("recovery continuation Job identity is invalid")
        if not job.configuration_snapshot_id or not job.configuration_snapshot_digest:
            raise ValueError("recovery continuation Job has no snapshot pin")
        continuation = self._repository.get_recovery_continuation_for_job(job_id)
        if continuation is None:
            raise LookupError(f"recovery continuation for Job {job_id!r} was not found")
        if continuation.status not in _ACTIVE_STATUSES:
            raise ValueError("recovery continuation is not active")
        request = self._repository.get_recovery_request(continuation.request_id)
        task = self._repository.get_task(continuation.source_task_id)
        item = self._repository.get_item(continuation.source_item_id)
        if request is None or task is None or item is None:
            raise ValueError("recovery continuation linkage is unavailable")
        if not request.active:
            raise ValueError("recovery request is no longer active")
        if (
            request.task_id != continuation.source_task_id
            or request.item_id != continuation.source_item_id
            or item.task_id != continuation.source_task_id
            or item.item_id != continuation.source_item_id
            or item.status is not TaskItemStatus.PENDING
            or item.stage != "task_retry_requested"
        ):
            raise ValueError("recovery continuation source eligibility changed")
        if (
            task.configuration_snapshot_id != continuation.configuration_snapshot_id
            or task.configuration_snapshot_digest != continuation.configuration_snapshot_digest
            or request.configuration_snapshot_id != continuation.configuration_snapshot_id
            or request.configuration_snapshot_digest != continuation.configuration_snapshot_digest
            or job.configuration_snapshot_id != continuation.configuration_snapshot_id
            or job.configuration_snapshot_digest != continuation.configuration_snapshot_digest
        ):
            raise ValueError("recovery continuation configuration snapshot changed")
        active = self._repository.get_active_recovery_request(item.item_id)
        if active is None or active.request_id != continuation.request_id:
            raise ValueError("recovery request is no longer the active request")
        return PreparedRecoveryContinuation(continuation, request, item)

    def started(self, job_id: str) -> RecoveryContinuation:
        return self._repository.mark_recovery_continuation_running(job_id)

    def cancelled(self, job_id: str) -> RecoveryContinuation:
        return self._repository.cancel_recovery_continuation(job_id)

    def finish(self, job_id: str, task_id: str) -> RecoveryContinuation:
        task = self._repository.get_task(task_id)
        if task is None:
            return self._repository.complete_recovery_continuation(
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
            return self._repository.complete_recovery_continuation(
                job_id,
                new_task_id=task_id,
                new_result_id=result_id,
                success=True,
            )
        if items and items[0].status in _WAITING_STATUSES:
            error = "continued analysis requires a human decision"
            recovery = "resolve the new item's review or conflict, then continue only that new item"
        elif items and items[0].error:
            error = "single-item DryRun analysis failed"
            recovery = _RECOVERY
        else:
            error = "single-item DryRun did not produce a completed Preview/Result"
            recovery = _RECOVERY
        return self._repository.complete_recovery_continuation(
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
    ) -> None:
        error = (
            "saved configuration snapshot is unavailable"
            if snapshot_unavailable
            else "continuation linkage or eligibility validation failed before pipeline"
            if preflight
            else "recovery continuation failed before Task completion"
        )
        recovery = (
            "restore the saved published revision, or create a new recovery request under "
            "the current Active configuration"
            if snapshot_unavailable
            else "inspect the linked Task/TaskItem, repair the stale condition, then "
            "continue only this item"
            if preflight
            else _RECOVERY
        )
        try:
            if queued:
                self._repository.fail_queued_recovery_continuation(
                    job_id, error=error, recovery=recovery
                )
            else:
                self._repository.complete_recovery_continuation(
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
