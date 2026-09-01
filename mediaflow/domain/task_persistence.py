from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from mediaflow.domain.manual_execution import (
    ManualExecution,
    ManualExecutionAuthorization,
    ManualExecutionAuthorizationAudit,
    ManualExecutionEffect,
    ManualExecutionItem,
)
from mediaflow.domain.manual_organize_preview import (
    ManualOrganizePreview,
    ManualPreviewItem,
)
from mediaflow.domain.recovery import RecoveryRequest


class PersistentTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskItemStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DRY_RUN = "dry_run"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    WAITING_CONFIRM = "waiting_confirm"
    WAITING_RECOGNITION = "waiting_recognition"
    WAITING_METADATA = "waiting_metadata"
    WAITING_METADATA_CORRECTION = "waiting_metadata_correction"
    WAITING_CLASSIFICATION = "waiting_classification"
    PAUSED = "paused"
    IGNORED = "ignored"

    @property
    def retryable(self) -> bool:
        return self in {
            self.PROCESSING,
            self.PARTIAL,
            self.FAILED,
            self.CANCELLED,
            self.PAUSED,
        }


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
    pause_requested: bool = False
    scope_path: str | None = None
    item_limit: int | None = None
    configuration_snapshot_id: str | None = None
    configuration_snapshot_digest: str | None = None


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
    completed_operations: tuple[str, ...] = ()
    attachment_count: int = 0
    retry_attempts: int = 0
    retry_category: str | None = None
    cleanup_status: str | None = None
    cleanup_step_count: int = 0
    # Added in runtime schema 23.  Legacy result rows remain ``unknown`` rather than
    # deriving effect certainty from status or the historical operation list.
    effect_certainty: str = "unknown"
    uncertain_effects: tuple[str, ...] = ()


class ConfirmationStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class ConflictConfirmation:
    confirmation_id: str
    task_id: str
    item_id: str
    plan_id: str
    conflict_type: str
    source_storage_id: str
    source_path: str
    destination_storage_id: str
    destination_path: str
    configured_strategy: str
    status: ConfirmationStatus
    created_at: datetime
    updated_at: datetime
    selected_strategy: str | None = None
    proposed_destination_path: str | None = None
    overwrite_authorized: bool = False
    actor: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class ConflictDecisionAudit:
    audit_id: str
    confirmation_id: str
    strategy: str
    decided_at: datetime
    overwrite_authorized: bool
    actor: str | None = None
    note: str | None = None


class PersistentTaskRepository(Protocol):
    def create_manual_preview(
        self,
        preview: ManualOrganizePreview,
        items: tuple[ManualPreviewItem, ...] | list[ManualPreviewItem] | None = None,
    ) -> ManualOrganizePreview: ...
    def get_manual_preview(self, preview_id: str) -> ManualOrganizePreview | None: ...
    def list_manual_previews(
        self, intent_id: str, *, limit: int = 100
    ) -> tuple[ManualOrganizePreview, ...]: ...
    def get_latest_manual_preview(self, intent_id: str) -> ManualOrganizePreview | None: ...
    def mark_manual_preview_items_stale(
        self,
        intent_id: str,
        item_ids: tuple[str, ...] | list[str],
        reason: str,
        now: datetime,
    ) -> int: ...
    def create_manual_execution_authorization(
        self, authorization: ManualExecutionAuthorization
    ) -> None: ...
    def get_manual_execution_authorization(
        self, authorization_id: str
    ) -> ManualExecutionAuthorization | None: ...
    def list_manual_execution_authorizations(
        self, *, limit: int = 100
    ) -> tuple[ManualExecutionAuthorization, ...]: ...
    def list_manual_execution_authorization_audit(
        self, authorization_id: str
    ) -> tuple[ManualExecutionAuthorizationAudit, ...]: ...
    def expire_manual_execution_authorizations(self, now: datetime) -> int: ...
    def admit_manual_execution(
        self,
        authorization: ManualExecutionAuthorization,
        execution: ManualExecution,
        items: tuple[ManualExecutionItem, ...],
        locks: tuple[tuple[str, str], ...],
        now: datetime,
    ) -> ManualExecution: ...
    def get_manual_execution(self, execution_id: str) -> ManualExecution | None: ...
    def update_manual_execution(self, execution: ManualExecution) -> None: ...
    def update_manual_execution_item(self, item: ManualExecutionItem) -> None: ...
    def complete_manual_execution_item(
        self,
        execution: ManualExecution,
        item: ManualExecutionItem,
        task_item: PersistentTaskItem,
        task: PersistentTask,
        result: PersistentResultRecord,
        effects: tuple[ManualExecutionEffect, ...],
        locks: tuple[tuple[str, str], ...],
    ) -> None: ...
    def reconcile_manual_execution(
        self,
        execution: ManualExecution,
        items: tuple[ManualExecutionItem, ...],
        task_items: tuple[PersistentTaskItem, ...],
        task: PersistentTask,
        results: tuple[PersistentResultRecord, ...],
        effects: tuple[ManualExecutionEffect, ...],
        audit: ManualExecutionAuthorizationAudit,
    ) -> None: ...
    def create_task(self, task: PersistentTask) -> None: ...
    def update_task(self, task: PersistentTask) -> None: ...
    def request_task_pause(self, task_id: str, updated_at: datetime) -> PersistentTask: ...
    def task_pause_requested(self, task_id: str) -> bool: ...
    def get_task(self, task_id: str) -> PersistentTask | None: ...
    def list_tasks(
        self,
        *,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[PersistentTask, ...]: ...
    def upsert_item(self, item: PersistentTaskItem) -> None: ...
    def get_item(self, item_id: str) -> PersistentTaskItem | None: ...
    def list_items(
        self,
        task_id: str,
        *,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[PersistentTaskItem, ...]: ...
    def append_result(self, result: PersistentResultRecord) -> None: ...
    def list_results(
        self,
        task_id: str,
        *,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[PersistentResultRecord, ...]: ...
    def get_latest_result_for_source(
        self, storage_id: str, path: str
    ) -> PersistentResultRecord | None: ...
    def create_confirmation(self, confirmation: ConflictConfirmation) -> None: ...
    def get_confirmation(self, confirmation_id: str) -> ConflictConfirmation | None: ...
    def list_confirmations(
        self, *, status: ConfirmationStatus | None = None, limit: int | None = None
    ) -> tuple[ConflictConfirmation, ...]: ...
    def resolve_confirmation(
        self,
        confirmation: ConflictConfirmation,
        audit: ConflictDecisionAudit,
        item: PersistentTaskItem | None = None,
    ) -> None: ...
    def list_confirmation_audit(
        self, confirmation_id: str
    ) -> tuple[ConflictDecisionAudit, ...]: ...
    def get_processing_checkpoint_context(
        self, item_id: str, *, result_limit: int = 32, audit_limit: int = 64
    ): ...
    def list_recovery_requests(
        self, item_id: str, *, limit: int = 32
    ) -> tuple[RecoveryRequest, ...]: ...
    def get_active_recovery_request(self, item_id: str) -> RecoveryRequest | None: ...
    def admit_recovery_request(
        self, request: RecoveryRequest, *, expected_checkpoint_version: str
    ): ...


class FileOperationLockRepository(Protocol):
    def acquire(self, storage_id: str, path: str, task_id: str, acquired_at: datetime) -> bool: ...
    def lock_owned(self, storage_id: str, path: str, task_id: str) -> bool: ...
    def release(self, storage_id: str, path: str, task_id: str) -> None: ...
    def reclaim_task_locks(self, task_id: str) -> int: ...
