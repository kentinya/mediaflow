from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
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
from mediaflow.domain.manual_safety import redact_evidence_text, redact_evidence_value
from mediaflow.domain.recovery import RecoveryRequest

#: The command recorded by the Web-native manual Organize admission path.  That
#: Task is executed synchronously inside the admitting API request, so it
#: observes neither a durable pause request nor a durable Task cancellation and
#: advertises no Web lifecycle control.
MANUAL_ORGANIZE_TASK_COMMAND = "manual_organize"

#: The command recorded by one bounded single-item direct Files command
#: (Create Folder, Create Text File, Rename or Text Save).  It is executed
#: synchronously inside the admitting API request with one durable item.
FILES_DIRECT_COMMAND_TASK = "files_direct_command"

#: The command recorded by a bounded multi-item or recursive Files Delete.
#: It runs as one Task with independent per-item outcomes and recovery.
FILES_DELETE_TASK_COMMAND = "files_delete"

#: The command recorded by a bounded Files Copy/Move transfer.  Every transfer
#: runs as one durable Task admitted before the first Storage mutation and
#: executed by the resident Worker under a persisted claim fence, with
#: independent per-item/per-entry outcomes.
FILES_TRANSFER_TASK_COMMAND = "files_transfer"


#: The durable admission/claim status of one bounded Files transfer.  The
#: transfer row — not the Task row — is the Worker claim authority: only an
#: ``admitted`` transfer (or one whose previous lease expired) can be claimed,
#: and only the current claim owner may advance its progress or publish a
#: terminal status.
class FilesTransferStatus(StrEnum):
    ADMITTED = "admitted"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in {
            FilesTransferStatus.COMPLETED,
            FilesTransferStatus.PARTIAL_SUCCESS,
            FilesTransferStatus.FAILED,
            FilesTransferStatus.CANCELLED,
        }


#: The files_transfers row: the bounded, claimable admission record of one
#: Copy/Move transfer.  ``authority_json`` pins the exact confirmed operation
#: (pinned configuration revision/digest, endpoint ResourceLibrary/Storage
#: identities, normalized logical paths, operation, conflict choice, confirmed
#: entry scope and pinned keep-both destinations) so a Worker reconstructs the
#: exact confirmed work after a process restart.  It never carries host roots,
#: credentials, provider payloads or content.
@dataclass(frozen=True)
class PersistentFilesTransfer:
    transfer_id: str
    task_id: str
    status: FilesTransferStatus
    authority_json: str
    configuration_snapshot_id: str
    configuration_snapshot_digest: str
    worker_id: str | None = None
    claim_token: str | None = None
    claimed_at: datetime | None = None
    claim_expires_at: datetime | None = None
    attempts: int = 0
    error: str | None = None
    next_action: str | None = None
    created_at: datetime = datetime.min.replace(tzinfo=UTC)
    updated_at: datetime = datetime.min.replace(tzinfo=UTC)
    completed_at: datetime | None = None


#: Task-item stage recorded for a transfer item the running process never
#: completed: the process ended (or lost the item) between admission and the
#: final per-item outcome record.  The recorded entry progress before the
#: marker stays the only known-safe evidence; the item is an explicit
#: interrupted/investigation state and is never silently retried.
TRANSFER_INTERRUPTED_STAGE = "transfer_interrupted"


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
    source_occurrence_id: str | None = None
    source_fingerprint: str | None = None
    source_fingerprint_state: str = "unverified"
    # Added in runtime schema 35: the bounded in-flight transfer progress of one
    # direct Files Copy/Move item.  A JSON object with aggregate counters and a
    # truncated per-entry list, or None for non-transfer items.  It is only an
    # in-flight marker: once the terminal item outcome is persisted, the field
    # is cleared and the Result carries the authoritative identity/checkpoints.
    progress: str | None = None


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
    source_occurrence_id: str | None = None
    source_fingerprint: str | None = None
    source_fingerprint_state: str = "unverified"


def redact_persistent_result(
    result: PersistentResultRecord, *, redact_identity: bool = False
) -> PersistentResultRecord:
    """Return a secret-free Result while preserving its identity fields.

    Source and destination paths are also used as FileIndex and plan lookup
    keys, so they remain exact by default. Display projections can opt into
    redacting those identity strings without changing the persisted lookup
    values or execution behavior.
    """

    return replace(
        result,
        source_path=redact_evidence_text(result.source_path)
        if redact_identity
        else result.source_path,
        destination_path=(
            redact_evidence_text(result.destination_path)
            if redact_identity and result.destination_path is not None
            else result.destination_path
        ),
        title=redact_evidence_text(result.title) if result.title is not None else None,
        error=redact_evidence_text(result.error) if result.error is not None else None,
        completed_operations=tuple(
            redact_evidence_text(value) if isinstance(value, str) else redact_evidence_value(value)
            for value in result.completed_operations
        ),
        uncertain_effects=tuple(
            redact_evidence_text(value) if isinstance(value, str) else redact_evidence_value(value)
            for value in result.uncertain_effects
        ),
    )


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
    def list_manual_execution_authorizations_for_preview(
        self, preview_id: str, *, limit: int = 100
    ) -> tuple[ManualExecutionAuthorization, ...]: ...
    def list_manual_execution_authorizations_for_intent(
        self, intent_id: str, *, limit: int = 100
    ) -> tuple[ManualExecutionAuthorization, ...]: ...
    def list_manual_execution_authorization_audit(
        self, authorization_id: str
    ) -> tuple[ManualExecutionAuthorizationAudit, ...]: ...
    def expire_manual_execution_authorizations(self, now: datetime) -> int: ...
    def revoke_manual_execution_authorization(
        self,
        authorization_id: str,
        now: datetime,
        *,
        actor: str | None = None,
        reason: str = "request_rejected",
    ) -> bool: ...
    def admit_manual_execution(
        self,
        authorization: ManualExecutionAuthorization,
        execution: ManualExecution,
        items: tuple[ManualExecutionItem, ...],
        locks: tuple[tuple[str, str], ...],
        now: datetime,
    ) -> ManualExecution: ...
    def get_manual_execution(self, execution_id: str) -> ManualExecution | None: ...
    def list_manual_executions_for_preview(
        self, preview_id: str, *, limit: int = 100
    ) -> tuple[ManualExecution, ...]: ...
    def list_manual_executions_for_intent(
        self, intent_id: str, *, limit: int = 100
    ) -> tuple[ManualExecution, ...]: ...
    def list_manual_executions_for_task(
        self, task_id: str, *, limit: int = 100
    ) -> tuple[ManualExecution, ...]: ...
    def list_manual_executions_for_task_item(
        self, task_id: str, task_item_id: str, *, limit: int = 100
    ) -> tuple[ManualExecution, ...]: ...
    def list_manual_executions_for_source(
        self, storage_id: str, path: str, *, limit: int = 100
    ) -> tuple[ManualExecution, ...]: ...
    def update_manual_execution(self, execution: ManualExecution) -> None: ...
    def claim_next_manual_execution(
        self,
        now: datetime,
        *,
        worker_id: str,
        claim_token: str,
        lease_seconds: float,
    ) -> ManualExecution | None: ...
    def manual_execution_claim(self, execution_id: str) -> dict[str, object] | None: ...
    def begin_manual_execution(
        self, execution_id: str, claim_token: str, now: datetime
    ) -> bool: ...
    def heartbeat_manual_execution_claim(
        self,
        execution_id: str,
        claim_token: str,
        now: datetime,
        lease_seconds: float,
    ) -> bool: ...
    def release_manual_execution_claim(self, execution_id: str, claim_token: str) -> bool: ...
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
    def admit_files_transfer(
        self,
        task: PersistentTask,
        items: tuple[PersistentTaskItem, ...],
        transfer: PersistentFilesTransfer,
    ) -> None: ...
    def get_files_transfer(self, transfer_id: str) -> PersistentFilesTransfer | None: ...
    def get_files_transfer_for_task(self, task_id: str) -> PersistentFilesTransfer | None: ...
    def claim_next_files_transfer(
        self,
        now: datetime,
        *,
        worker_id: str,
        claim_token: str,
        lease_seconds: float,
    ) -> PersistentFilesTransfer | None: ...
    def begin_files_transfer(self, transfer_id: str, claim_token: str, now: datetime) -> bool: ...
    def heartbeat_files_transfer_claim(
        self,
        transfer_id: str,
        claim_token: str,
        now: datetime,
        lease_seconds: float,
    ) -> bool: ...
    def finish_files_transfer(
        self,
        transfer: PersistentFilesTransfer,
        *,
        claim_token: str,
        now: datetime,
    ) -> bool: ...
    def pause_files_transfer(
        self, transfer_id: str, *, claim_token: str, now: datetime
    ) -> bool: ...
    def requeue_files_transfer(
        self, transfer_id: str, now: datetime
    ) -> PersistentFilesTransfer: ...
    def transfer_claim_is_current(
        self, transfer_id: str, claim_token: str, now: datetime
    ) -> bool: ...
    def request_task_pause(self, task_id: str, updated_at: datetime) -> PersistentTask: ...
    def pause_task_if_current(
        self,
        task_id: str,
        *,
        updated_at: datetime,
        expected_version: str | None = None,
    ) -> PersistentTask | None: ...
    def cancel_task_if_current(
        self,
        task_id: str,
        *,
        updated_at: datetime,
        expected_version: str | None = None,
    ) -> PersistentTask | None: ...
    def task_pause_requested(self, task_id: str) -> bool: ...
    def get_task(self, task_id: str) -> PersistentTask | None: ...
    def list_tasks(
        self,
        *,
        limit: int | None = None,
        after: tuple[datetime, str] | None = None,
        before: tuple[datetime, str] | None = None,
        status: str | None = None,
        command: str | None = None,
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
