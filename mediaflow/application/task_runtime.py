from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from mediaflow.application.media_organizer import (
    MediaOrganizerBatchResult,
    MediaOrganizerItemResult,
)
from mediaflow.domain.media_evidence import PipelineEvidence
from mediaflow.domain.organizer import (
    ExecutionEffectCertainty,
    ExecutionStatus,
    OrganizePlan,
    OrganizePolicy,
)
from mediaflow.domain.task_persistence import (
    FileOperationLockRepository,
    PersistentResultRecord,
    PersistentTask,
    PersistentTaskItem,
    PersistentTaskRepository,
    PersistentTaskStatus,
    TaskItemStatus,
)


class TaskLockError(RuntimeError):
    pass


class TaskPauseRequested(RuntimeError):
    pass


class PersistentTaskCoordinator:
    """Persists orchestration state without owning any media strategy decision."""

    def __init__(
        self,
        repository: PersistentTaskRepository,
        locks: FileOperationLockRepository,
    ) -> None:
        self.repository = repository
        self.locks = locks

    def create(
        self,
        command: str,
        *,
        execute_authorized: bool,
        scope_path: str | None = None,
        item_limit: int | None = None,
        configuration_snapshot_id: str | None = None,
        configuration_snapshot_digest: str | None = None,
        require_configuration_snapshot: bool = False,
    ) -> PersistentTask:
        if item_limit is not None and item_limit < 1:
            raise ValueError("task item limit must be positive")
        if (configuration_snapshot_id is None) != (configuration_snapshot_digest is None):
            raise ValueError("Task configuration snapshot ID and digest must be provided together")
        if require_configuration_snapshot and (
            not configuration_snapshot_id or not configuration_snapshot_digest
        ):
            raise ValueError("managed Task creation requires a configuration snapshot pin")
        now = datetime.now(UTC)
        task = PersistentTask(
            str(uuid4()),
            command,
            PersistentTaskStatus.RUNNING,
            execute_authorized,
            now,
            now,
            started_at=now,
            scope_path=scope_path,
            item_limit=item_limit,
            configuration_snapshot_id=configuration_snapshot_id,
            configuration_snapshot_digest=configuration_snapshot_digest,
        )
        self.repository.create_task(task)
        return task

    def reopen(self, task_id: str, *, execute: bool) -> PersistentTask:
        task = self.require(task_id)
        if execute and not task.execute_authorized:
            raise ValueError(
                "original task was not execute-authorized; retry cannot enable execute"
            )
        now = datetime.now(UTC)
        reopened = replace(
            task,
            status=PersistentTaskStatus.RUNNING,
            updated_at=now,
            completed_at=None,
            error=None,
            pause_requested=False,
        )
        self.locks.reclaim_task_locks(task_id)
        self.repository.update_task(reopened)
        return reopened

    def require(self, task_id: str) -> PersistentTask:
        task = self.repository.get_task(task_id)
        if task is None:
            raise LookupError(f"task {task_id!r} was not found")
        return task

    def begin_item(
        self,
        task_id: str,
        storage_id: str,
        resource_library_id: str,
        source_path: str,
        source_display: str,
    ) -> PersistentTaskItem:
        task = self.require(task_id)
        if task.status is not PersistentTaskStatus.RUNNING:
            raise RuntimeError(f"task {task_id!r} is not running")
        if task.pause_requested or self.repository.task_pause_requested(task_id):
            raise TaskPauseRequested(f"task {task_id!r} pause was requested")
        item_id = str(uuid5(NAMESPACE_URL, f"{task_id}:{storage_id}:{source_path}"))
        previous = self.repository.get_item(item_id)
        now = datetime.now(UTC)
        item = PersistentTaskItem(
            item_id,
            task_id,
            storage_id,
            resource_library_id,
            source_path,
            source_display,
            TaskItemStatus.PROCESSING,
            "pipeline",
            (previous.attempts if previous else 0) + 1,
            previous.created_at if previous else now,
            now,
        )
        self.repository.upsert_item(item)
        if not self.locks.acquire(storage_id, source_path, task_id, now):
            failed = replace(
                item,
                status=TaskItemStatus.FAILED,
                stage="lock",
                error="source is locked by another active task",
                updated_at=datetime.now(UTC),
            )
            self.repository.upsert_item(failed)
            raise TaskLockError(failed.error)
        return item

    def cancel(self, task_id: str) -> PersistentTask:
        task = self.require(task_id)
        now = datetime.now(UTC)
        for item in self.repository.list_items(task_id):
            if item.status in {
                TaskItemStatus.PENDING,
                TaskItemStatus.PROCESSING,
                TaskItemStatus.PAUSED,
            }:
                self.repository.upsert_item(
                    replace(
                        item,
                        status=TaskItemStatus.CANCELLED,
                        stage="cancelled",
                        updated_at=now,
                        error="task cancelled",
                    )
                )
        cancelled = replace(
            task,
            status=PersistentTaskStatus.CANCELLED,
            updated_at=now,
            completed_at=now,
            error="task cancelled",
        )
        self.repository.update_task(cancelled)
        self.locks.reclaim_task_locks(task_id)
        return cancelled

    def request_pause(self, task_id: str) -> PersistentTask:
        return self.repository.request_task_pause(task_id, datetime.now(UTC))

    def pause_requested(self, task_id: str) -> bool:
        return self.repository.task_pause_requested(task_id)

    def acknowledge_pause(self, task_id: str) -> PersistentTask:
        task = self.require(task_id)
        if task.status is PersistentTaskStatus.PAUSED:
            return task
        if task.status is not PersistentTaskStatus.RUNNING or not task.pause_requested:
            raise ValueError("only a running task with a pause request can be paused")
        now = datetime.now(UTC)
        for item in self.repository.list_items(task_id):
            if item.status in {TaskItemStatus.PENDING, TaskItemStatus.PROCESSING}:
                self.repository.upsert_item(
                    replace(
                        item,
                        status=TaskItemStatus.PAUSED,
                        stage="paused",
                        updated_at=now,
                        error=None,
                    )
                )
        paused = replace(
            task,
            status=PersistentTaskStatus.PAUSED,
            updated_at=now,
            completed_at=None,
            error=None,
            pause_requested=False,
        )
        self.repository.update_task(paused)
        self.locks.reclaim_task_locks(task_id)
        return paused

    def record_discovered(
        self,
        task_id: str,
        storage_id: str,
        resource_library_id: str,
        source_path: str,
        source_display: str,
    ) -> PersistentTaskItem:
        now = datetime.now(UTC)
        item = PersistentTaskItem(
            str(uuid5(NAMESPACE_URL, f"{task_id}:{storage_id}:{source_path}")),
            task_id,
            storage_id,
            resource_library_id,
            source_path,
            source_display,
            TaskItemStatus.SKIPPED,
            "scanned",
            0,
            now,
            now,
        )
        self.repository.upsert_item(item)
        return item

    def complete_item(self, item: PersistentTaskItem, result: MediaOrganizerItemResult) -> None:
        now = datetime.now(UTC)
        execution = result.execution
        if result.error:
            status = TaskItemStatus.FAILED
        elif execution is None:
            status = TaskItemStatus.SKIPPED
        else:
            status = {
                ExecutionStatus.SUCCESS: TaskItemStatus.SUCCESS,
                ExecutionStatus.DRY_RUN: TaskItemStatus.DRY_RUN,
                ExecutionStatus.PARTIAL: TaskItemStatus.PARTIAL,
                ExecutionStatus.FAILED: TaskItemStatus.FAILED,
                ExecutionStatus.SKIPPED: TaskItemStatus.SKIPPED,
            }[execution.status]
        plan = result.plan
        completed = replace(
            item,
            status=status,
            stage="completed" if not status.retryable else "failed",
            updated_at=now,
            plan_id=plan.plan_id if plan else None,
            destination_storage_id=(
                plan.destination_location.storage_id if plan and plan.destination_location else None
            ),
            destination_path=(
                plan.destination_location.path if plan and plan.destination_location else None
            ),
            execution_status=execution.status.value if execution else None,
            error=result.error
            or ("; ".join(execution.errors) if execution and execution.errors else None),
        )
        try:
            atomic = getattr(self.repository, "complete_item_with_evidence", None)
            if callable(atomic):
                atomic(completed, self._result(completed, result, now), result.evidence)
            else:
                self.repository.append_result(self._result(completed, result, now))
                self.repository.upsert_item(completed)
                if result.evidence is not None:
                    self.record_evidence(result.evidence)
        finally:
            self.locks.release(item.storage_id, item.source_path, item.task_id)

    def record_evidence(self, evidence: PipelineEvidence) -> None:
        """Persist one bounded evidence record at a TaskItem boundary."""

        append = getattr(self.repository, "append_evidence", None)
        if callable(append):
            append(evidence)

    def wait_for_confirmation(
        self,
        item: PersistentTaskItem,
        plan: OrganizePlan,
        policy: OrganizePolicy,
        *,
        evidence: PipelineEvidence | None = None,
    ) -> None:
        from mediaflow.application.conflict_resolution import ConfirmationService

        now = datetime.now(UTC)
        waiting = replace(
            item,
            status=TaskItemStatus.WAITING_CONFIRM,
            stage="waiting_confirm",
            updated_at=now,
            plan_id=plan.plan_id,
            destination_storage_id=plan.target_storage_id,
            destination_path=(
                plan.destination_location.path if plan.destination_location else plan.target
            ),
            error=None,
        )
        ConfirmationService(self.repository).create(
            task_id=item.task_id,
            item_id=item.item_id,
            plan=plan,
            policy=policy,
            item=waiting,
            evidence=evidence,
        )
        self.locks.release(item.storage_id, item.source_path, item.task_id)

    def wait_for_metadata(
        self,
        item,
        identification,
        metadata_policy_id: str,
        *,
        evidence: PipelineEvidence | None = None,
    ) -> None:
        from mediaflow.application.metadata_review import MetadataReviewService

        MetadataReviewService(self.repository).create(
            item, identification, metadata_policy_id, evidence=evidence
        )
        self.locks.release(item.storage_id, item.source_path, item.task_id)

    def wait_for_recognition(
        self,
        item,
        recognition,
        recognition_types,
        *,
        evidence: PipelineEvidence | None = None,
    ) -> None:
        from mediaflow.application.recognition_review import RecognitionReviewService

        RecognitionReviewService(self.repository, recognition_types).create(
            item, recognition, evidence=evidence
        )
        self.locks.release(item.storage_id, item.source_path, item.task_id)

    def wait_for_metadata_correction(
        self,
        item,
        identification,
        policy,
        parsed,
        *,
        evidence: PipelineEvidence | None = None,
    ) -> None:
        from mediaflow.application.metadata_correction import MetadataCorrectionService

        MetadataCorrectionService(self.repository, (policy,)).create(
            item, identification, policy, parsed, evidence=evidence
        )
        self.locks.release(item.storage_id, item.source_path, item.task_id)

    def wait_for_classification(
        self,
        item,
        result,
        policy,
        identity,
        *,
        evidence: PipelineEvidence | None = None,
    ) -> None:
        from mediaflow.application.classification_review import ClassificationReviewService

        ClassificationReviewService(self.repository).create(
            item, result, policy, identity, evidence=evidence
        )
        self.locks.release(item.storage_id, item.source_path, item.task_id)

    def finish(self, task_id: str, batch: MediaOrganizerBatchResult) -> PersistentTask:
        task = self.require(task_id)
        items = self.repository.list_items(task_id)
        failed = sum(
            item.status in {TaskItemStatus.FAILED, TaskItemStatus.PARTIAL} for item in items
        )
        waiting_statuses = {
            TaskItemStatus.WAITING_CONFIRM,
            TaskItemStatus.WAITING_RECOGNITION,
            TaskItemStatus.WAITING_METADATA,
            TaskItemStatus.WAITING_METADATA_CORRECTION,
            TaskItemStatus.WAITING_CLASSIFICATION,
        }
        waiting = sum(item.status in waiting_statuses for item in items)
        ignored = sum(item.status is TaskItemStatus.IGNORED for item in items)
        completed = sum(
            not item.status.retryable
            and item.status not in waiting_statuses
            and item.status is not TaskItemStatus.IGNORED
            for item in items
        )
        status = (
            PersistentTaskStatus.PARTIAL_SUCCESS
            if waiting or ignored or (failed and completed)
            else PersistentTaskStatus.FAILED
            if failed or batch.scan_errors
            else PersistentTaskStatus.COMPLETED
        )
        now = datetime.now(UTC)
        final = replace(
            task,
            status=status,
            updated_at=now,
            completed_at=now,
            total_items=len(items),
            completed_items=completed,
            failed_items=failed + len(batch.scan_errors),
            error="scan errors occurred" if batch.scan_errors else None,
        )
        self.repository.update_task(final)
        return final

    def retryable_items(self, task_id: str, *, failed_only: bool) -> tuple[PersistentTaskItem, ...]:
        self.require(task_id)
        statuses = (
            {TaskItemStatus.FAILED, TaskItemStatus.PARTIAL}
            if failed_only
            else {
                TaskItemStatus.PENDING,
                TaskItemStatus.PROCESSING,
                TaskItemStatus.FAILED,
                TaskItemStatus.PARTIAL,
                TaskItemStatus.CANCELLED,
                TaskItemStatus.PAUSED,
            }
        )
        successful_results = {
            result.item_id
            for result in self.repository.list_results(task_id)
            if result.status
            in {
                TaskItemStatus.SUCCESS.value,
                TaskItemStatus.DRY_RUN.value,
                TaskItemStatus.SKIPPED.value,
            }
        }
        return tuple(
            item
            for item in self.repository.list_items(task_id)
            if item.status in statuses and item.item_id not in successful_results
        )

    @staticmethod
    def _result(
        item: PersistentTaskItem,
        result: MediaOrganizerItemResult,
        timestamp: datetime,
    ) -> PersistentResultRecord:
        strategy = result.strategy
        identity = strategy.metadata.identity if strategy and strategy.metadata else None
        plan = result.plan
        execution = result.execution
        effect_certainty, uncertain_effects = _effect_evidence(execution)
        return PersistentResultRecord(
            f"{item.item_id}:{item.attempts}",
            item.task_id,
            item.item_id,
            item.storage_id,
            item.source_path,
            item.destination_storage_id,
            item.destination_path,
            strategy.recognition.recognition_type_id if strategy else None,
            identity.provider if identity else None,
            identity.provider_id if identity else None,
            strategy.policy.metadata_policy_id if strategy and strategy.policy else None,
            strategy.policy.naming_policy_id if strategy and strategy.policy else None,
            strategy.policy.classification_policy_id if strategy and strategy.policy else None,
            strategy.policy.organize_policy_id if strategy and strategy.policy else None,
            execution.operation.value if execution else (plan.operation.value if plan else None),
            item.status.value,
            timestamp,
            identity.title if identity else None,
            item.error,
            execution.completed_operations if execution else (),
            len(plan.attachment_plans) if plan else 0,
            len(result.retry_events),
            result.retry_events[-1].category.value if result.retry_events else None,
            execution.cleanup_status.value if execution else None,
            len(execution.cleanup_steps) if execution else 0,
            effect_certainty,
            uncertain_effects,
        )


def _effect_evidence(execution) -> tuple[str, tuple[str, ...]]:
    """Persist only executor-owned effect evidence, never status/error inference."""
    if execution is None:
        # A failure before planning/execution is known to have no mutation in this invocation.
        return "none", ()
    try:
        certainty = ExecutionEffectCertainty(execution.effect_certainty)
    except (AttributeError, ValueError):
        return "unknown", ()
    return certainty.value, tuple(execution.uncertain_effects)
