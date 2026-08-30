"""Analysis-only recovery continuation contracts.

A recovery continuation turns one admitted, version-bound recovery request into
durable, bounded work: it re-enters the existing production pipeline for exactly
one TaskItem's original source scope under the item's pinned configuration
snapshot, produces a new linked Task/TaskItem/Result, and never grants execute,
overwrite, delete, source-cleanup or rollback authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from mediaflow.domain.automation import AutomationJob


class RecoveryContinuationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def active(self) -> bool:
        return self in {self.QUEUED, self.RUNNING}


class RecoveryContinuationReason(StrEnum):
    REQUEST_NOT_ACTIVE = "request_not_active"
    STALE_CHECKPOINT = "stale_checkpoint"
    SNAPSHOT_UNAVAILABLE = "snapshot_unavailable"
    NO_CONTINUATION_BOUNDARY = "no_continuation_boundary"
    CONTINUATION_EXISTS = "continuation_exists"
    QUEUE_FULL = "queue_full"
    UNKNOWN_ITEM = "unknown_item"
    ITEM_TASK_MISMATCH = "item_task_mismatch"
    INVALID_INPUT = "invalid_input"
    INVALID_VERSION = "invalid_checkpoint_version"
    INSUFFICIENT_AUTHORITY = "insufficient_authority"
    EXECUTE_REFUSED = "execute_refused"
    UNCERTAIN_EFFECTS = "uncertain_effects"
    ATOMIC_COMMIT_FAILED = "atomic_commit_failed"


class RecoveryContinuationError(ValueError):
    """A bounded, auditable refusal from the recovery continuation submission."""

    def __init__(
        self,
        reason: RecoveryContinuationReason,
        message: str,
        *,
        current_checkpoint_version: str | None = None,
        existing_continuation: RecoveryContinuation | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = RecoveryContinuationReason(reason)
        self.current_checkpoint_version = current_checkpoint_version
        self.existing_continuation = existing_continuation


# The shorter name keeps call sites compact while the longer name stays
# discoverable for transport vocabulary that references these rejections.
RecoveryContinuationRejectionReason = RecoveryContinuationReason


@dataclass(frozen=True)
class RecoveryContinuation:
    """One durable, analysis-only continuation of an admitted request."""

    continuation_id: str
    request_id: str
    source_task_id: str
    source_item_id: str
    checkpoint_version: str
    configuration_snapshot_id: str
    configuration_snapshot_digest: str
    boundary: str
    status: RecoveryContinuationStatus
    created_at: datetime
    updated_at: datetime
    actor: str
    job_id: str
    new_task_id: str | None = None
    new_result_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    recovery: str | None = None
    authority_statement: str = (
        "analysis-only: no execute authority; no overwrite authority; no delete authority; "
        "no source-cleanup authority; no rollback authority"
    )

    @property
    def active(self) -> bool:
        return self.status.active

    def next_action(self) -> str:
        """One concrete, secret-free next step for the operator."""

        if self.status is RecoveryContinuationStatus.COMPLETED:
            return "inspect the linked DryRun Task/Result; the source item remains unchanged"
        if self.status is RecoveryContinuationStatus.FAILED:
            return (
                self.recovery
                or "inspect the failure, repair the stated condition, then continue this item again"
            )
        if self.status is RecoveryContinuationStatus.CANCELLED:
            return "refresh the Task item checkpoint and explicitly continue again"
        return "wait for the Worker, then inspect the linked DryRun Task/Result"

    def document(self) -> dict[str, object]:
        """Return a bounded transport-safe representation."""

        return {
            "continuation_id": self.continuation_id,
            "request_id": self.request_id,
            "source_task_id": self.source_task_id,
            "source_item_id": self.source_item_id,
            "checkpoint_version": self.checkpoint_version,
            "configuration_snapshot_id": self.configuration_snapshot_id,
            "configuration_snapshot_digest": self.configuration_snapshot_digest,
            "boundary": self.boundary,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "actor": self.actor,
            "job_id": self.job_id,
            "new_task_id": self.new_task_id,
            "new_result_id": self.new_result_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "recovery": self.recovery,
            "next_action": self.next_action(),
            "authority_statement": self.authority_statement,
        }


class RecoveryContinuationRepository(Protocol):
    def get_recovery_continuation_for_request(
        self, request_id: str
    ) -> RecoveryContinuation | None: ...
    def get_recovery_continuation_for_job(self, job_id: str) -> RecoveryContinuation | None: ...
    def list_recovery_continuations(
        self, item_id: str, *, limit: int = 32
    ) -> tuple[RecoveryContinuation, ...]: ...
    def admit_recovery_continuation(
        self,
        job: AutomationJob,
        continuation: RecoveryContinuation,
        *,
        maximum_active_jobs: int,
    ) -> tuple[RecoveryContinuation, bool]: ...
    def mark_recovery_continuation_running(
        self, job_id: str, now: datetime | None = None
    ) -> RecoveryContinuation: ...
    def bind_recovery_continuation_task(
        self, job_id: str, task_id: str
    ) -> RecoveryContinuation: ...
    def complete_recovery_continuation(
        self,
        job_id: str,
        *,
        new_task_id: str | None = None,
        new_result_id: str | None = None,
        success: bool,
        error: str | None = None,
        recovery: str | None = None,
        now: datetime | None = None,
    ) -> RecoveryContinuation: ...
    def fail_queued_recovery_continuation(
        self,
        job_id: str,
        *,
        error: str,
        recovery: str,
        now: datetime | None = None,
    ) -> RecoveryContinuation: ...
    def cancel_recovery_continuation(
        self, job_id: str, *, now: datetime | None = None
    ) -> RecoveryContinuation: ...
