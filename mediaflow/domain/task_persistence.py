from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class PersistentTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskItemStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DRY_RUN = "dry_run"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

    @property
    def retryable(self) -> bool:
        return self in {self.PROCESSING, self.PARTIAL, self.FAILED, self.CANCELLED}


@dataclass(frozen=True)
class PersistentTask:
    task_id: str
    command: str
    status: PersistentTaskStatus
    execute_authorized: bool
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    error: str | None = None


@dataclass(frozen=True)
class PersistentTaskItem:
    item_id: str
    task_id: str
    storage_id: str
    resource_library_id: str
    source_path: str
    source_display: str
    status: TaskItemStatus
    stage: str
    attempts: int
    created_at: datetime
    updated_at: datetime
    plan_id: str | None = None
    destination_storage_id: str | None = None
    destination_path: str | None = None
    execution_status: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class PersistentResultRecord:
    result_id: str
    task_id: str
    item_id: str
    source_storage_id: str
    source_path: str
    destination_storage_id: str | None
    destination_path: str | None
    recognition_type: str | None
    provider: str | None
    provider_id: str | None
    metadata_policy_id: str | None
    naming_policy_id: str | None
    classification_policy_id: str | None
    organize_policy_id: str | None
    operation: str | None
    status: str
    created_at: datetime
    title: str | None = None
    error: str | None = None


class PersistentTaskRepository(Protocol):
    def create_task(self, task: PersistentTask) -> None: ...
    def update_task(self, task: PersistentTask) -> None: ...
    def get_task(self, task_id: str) -> PersistentTask | None: ...
    def list_tasks(self, *, limit: int | None = None) -> tuple[PersistentTask, ...]: ...
    def upsert_item(self, item: PersistentTaskItem) -> None: ...
    def get_item(self, item_id: str) -> PersistentTaskItem | None: ...
    def list_items(self, task_id: str) -> tuple[PersistentTaskItem, ...]: ...
    def append_result(self, result: PersistentResultRecord) -> None: ...
    def list_results(self, task_id: str) -> tuple[PersistentResultRecord, ...]: ...


class FileOperationLockRepository(Protocol):
    def acquire(self, storage_id: str, path: str, task_id: str, acquired_at: datetime) -> bool: ...
    def release(self, storage_id: str, path: str, task_id: str) -> None: ...
    def reclaim_task_locks(self, task_id: str) -> int: ...
