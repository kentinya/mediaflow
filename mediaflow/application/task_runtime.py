from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from mediaflow.application.media_organizer import (
    MediaOrganizerBatchResult,
    MediaOrganizerItemResult,
)
from mediaflow.domain.organizer import ExecutionStatus, OrganizePlan, OrganizePolicy
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


class PersistentTaskCoordinator:
    """Persists orchestration state without owning any media strategy decision."""

    def __init__(
        self,
        repository: PersistentTaskRepository,
        locks: FileOperationLockRepository,
    ) -> None:
        self.repository = repository
        self.locks = locks

    def create(self, command: str, *, execute_authorized: bool) -> PersistentTask:
        now = datetime.now(UTC)
        task = PersistentTask(
            str(uuid4()),
            command,
            PersistentTaskStatus.RUNNING,
            execute_authorized,
            now,
            now,
            started_at=now,
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
            if item.status in {TaskItemStatus.PENDING, TaskItemStatus.PROCESSING}:
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
            self.repository.append_result(self._result(completed, result, now))
            self.repository.upsert_item(completed)
        finally:
            self.locks.release(item.storage_id, item.source_path, item.task_id)

    def wait_for_confirmation(
        self, item: PersistentTaskItem, plan: OrganizePlan, policy: OrganizePolicy
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
        self.repository.upsert_item(waiting)
        ConfirmationService(self.repository).create(
            task_id=item.task_id, item_id=item.item_id, plan=plan, policy=policy
        )
        self.locks.release(item.storage_id, item.source_path, item.task_id)

    def wait_for_metadata(self, item, identification, metadata_policy_id: str) -> None:
        from mediaflow.application.metadata_review import MetadataReviewService

        MetadataReviewService(self.repository).create(item, identification, metadata_policy_id)
        self.locks.release(item.storage_id, item.source_path, item.task_id)

    def wait_for_classification(self, item, result, policy, identity) -> None:
        from mediaflow.application.classification_review import ClassificationReviewService

        ClassificationReviewService(self.repository).create(item, result, policy, identity)
        self.locks.release(item.storage_id, item.source_path, item.task_id)

    def finish(self, task_id: str, batch: MediaOrganizerBatchResult) -> PersistentTask:
        task = self.require(task_id)
        items = self.repository.list_items(task_id)
        failed = sum(
            item.status in {TaskItemStatus.FAILED, TaskItemStatus.PARTIAL} for item in items
        )
        waiting_statuses = {
            TaskItemStatus.WAITING_CONFIRM,
            TaskItemStatus.WAITING_METADATA,
            TaskItemStatus.WAITING_CLASSIFICATION,
        }
        waiting = sum(item.status in waiting_statuses for item in items)
        completed = sum(
            not item.status.retryable and item.status not in waiting_statuses for item in items
        )
        status = (
            PersistentTaskStatus.PARTIAL_SUCCESS
            if waiting or (failed and completed)
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
        )
