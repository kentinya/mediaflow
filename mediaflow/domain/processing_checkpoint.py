"""Durable, read-only projections for per-item processing recovery.

The checkpoint types deliberately describe facts and safe next actions only.  They do not
contain Storage or Provider handles and cannot grant execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from mediaflow.domain.failure import FailureExplanation

if TYPE_CHECKING:
    from mediaflow.domain.recovery import RecoveryRequest
    from mediaflow.domain.recovery_continuation import RecoveryContinuation
    from mediaflow.domain.task_persistence import (
        PersistentResultRecord,
        PersistentTask,
        PersistentTaskItem,
    )


class CheckpointStage(StrEnum):
    QUEUED = "queued"
    SCANNING = "scanning"
    PARSING = "parsing"
    STORAGE = "storage"
    PROCESSING = "processing"
    RECOGNITION = "recognition"
    METADATA = "metadata"
    NAMING = "naming"
    CLASSIFICATION = "classification"
    PLANNING = "planning"
    WAITING_CONFIRM = "waiting_confirm"
    WAITING_RECOGNITION = "waiting_recognition"
    WAITING_METADATA = "waiting_metadata"
    WAITING_METADATA_CORRECTION = "waiting_metadata_correction"
    WAITING_CLASSIFICATION = "waiting_classification"
    ORGANIZING = "organizing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    IGNORED = "ignored"
    UNKNOWN = "unknown"


class EffectCertainty(StrEnum):
    """What the persisted result can prove about media effects."""

    VERIFIED_COMPLETE = "verified_complete"
    ATTEMPTED_UNVERIFIED = "attempted_unverified"
    NONE = "none"
    UNKNOWN = "unknown"


class RetrySafety(StrEnum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    UNKNOWN = "unknown"


class ErrorCategory(StrEnum):
    NONE = "none"
    STORAGE = "storage"
    FILE = "file"
    PARSE = "parse"
    RECOGNITION = "recognition"
    METADATA = "metadata"
    NAMING = "naming"
    CLASSIFICATION = "classification"
    TRANSFER = "transfer"
    TIMEOUT = "timeout"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    DENIED_CAPABILITY = "denied_capability"
    DESTINATION_COLLISION = "destination_collision"
    ATTACHMENT_COLLISION = "attachment_collision"
    INVALID_DESTINATION = "invalid_destination"
    STORAGE_FAILURE = "storage_failure"
    PROVIDER_FAILURE = "provider_failure"
    UNCERTAIN_EFFECT = "uncertain_effect"
    PARTIAL_EFFECT = "partial_effect"
    UNSTABLE_SOURCE = "unstable_source"
    RECOGNITION_FAILURE = "recognition_failure"
    METADATA_FAILURE = "metadata_failure"
    NAMING_FAILURE = "naming_failure"
    CLASSIFICATION_FAILURE = "classification_failure"
    WORKFLOW_FAILURE = "workflow_failure"
    UNATTENDED_AUTHORITY = "unattended_authority"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CheckpointAction:
    action_id: str
    label: str
    confirmation_required: bool
    required_authority: str
    resolution_surface: str | None = None
    admissible: bool = False


@dataclass(frozen=True)
class CheckpointBlocker:
    kind: str
    blocker_id: str
    status: str
    task_id: str
    item_id: str
    resolution_path: str


@dataclass(frozen=True)
class CheckpointAudit:
    audit_id: str
    kind: str
    occurred_at: datetime
    actor: str | None = None


@dataclass(frozen=True)
class CheckpointConfiguration:
    snapshot_id: str | None
    snapshot_digest: str | None
    resolvable: bool | None
    reason: str | None


@dataclass(frozen=True)
class CheckpointResult:
    result_id: str
    status: str
    created_at: datetime
    recognition_type: str | None
    provider: str | None
    provider_id: str | None
    metadata_policy_id: str | None
    naming_policy_id: str | None
    classification_policy_id: str | None
    organize_policy_id: str | None
    operation: str | None
    destination_storage_id: str | None
    destination_path: str | None
    completed_operations: tuple[str, ...]
    effect_certainty: EffectCertainty
    uncertain_effects: tuple[str, ...]
    error_category: ErrorCategory
    retry_attempts: int
    cleanup_status: str | None
    failure: FailureExplanation | None = None


@dataclass(frozen=True)
class ProcessingCheckpointContext:
    """One bounded repository read used by every checkpoint surface."""

    task: PersistentTask
    item: PersistentTaskItem
    results: tuple[PersistentResultRecord, ...] = ()
    blockers: tuple[CheckpointBlocker, ...] = ()
    audits: tuple[CheckpointAudit, ...] = ()
    recovery_requests: tuple[RecoveryRequest, ...] = ()
    recovery_continuations: tuple[RecoveryContinuation, ...] = ()


class ProcessingCheckpointRepository(Protocol):
    def get_processing_checkpoint_context(
        self,
        item_id: str,
        *,
        result_limit: int = 32,
        audit_limit: int = 64,
    ) -> ProcessingCheckpointContext | None: ...

    def get_processing_checkpoint_contexts(
        self,
        item_ids: tuple[str, ...],
        *,
        result_limit: int = 32,
        audit_limit: int = 64,
    ) -> dict[str, ProcessingCheckpointContext]: ...


@dataclass(frozen=True)
class ProcessingCheckpoint:
    task_id: str
    item_id: str
    status: str
    raw_stage: str
    stage: CheckpointStage
    attempts: int
    source_storage_id: str
    resource_library_id: str
    source_path: str
    plan_id: str | None
    destination_storage_id: str | None
    destination_path: str | None
    configuration: CheckpointConfiguration
    latest_result: CheckpointResult | None
    prior_results: tuple[CheckpointResult, ...]
    blockers: tuple[CheckpointBlocker, ...]
    blocker: CheckpointBlocker | None
    audits: tuple[CheckpointAudit, ...]
    recovery_requests: tuple[RecoveryRequest, ...]
    recovery_continuation: RecoveryContinuation | None
    effect_certainty: EffectCertainty
    completed_operations: tuple[str, ...]
    uncertain_effects: tuple[str, ...]
    error_category: ErrorCategory
    retry_safety: RetrySafety
    actions: tuple[CheckpointAction, ...]
    refusal_reason: str | None
    checkpoint_version: str
    updated_at: datetime
    failure: FailureExplanation | None = None

    @property
    def permitted_action_ids(self) -> tuple[str, ...]:
        return tuple(action.action_id for action in self.actions)

    @property
    def active_recovery_request(self) -> RecoveryRequest | None:
        for request in reversed(self.recovery_requests):
            if request.active:
                return request
        return None

    def summary(self) -> dict[str, object]:
        """Small bounded projection embedded in task collection/detail rows."""

        return {
            "status": self.status,
            "stage": self.stage.value,
            "raw_stage": self.raw_stage,
            "blocker_kind": self.blocker.kind if self.blocker else None,
            "blocker_id": self.blocker.blocker_id if self.blocker else None,
            "effect_certainty": self.effect_certainty.value,
            "retry_safety": self.retry_safety.value,
            "permitted_action_ids": list(self.permitted_action_ids),
            "refusal_reason": self.refusal_reason,
            "checkpoint_version": self.checkpoint_version,
            "recovery_request": (
                self.active_recovery_request.document()
                if self.active_recovery_request is not None
                else None
            ),
            "recovery_continuation": (
                self.recovery_continuation.document()
                if self.recovery_continuation is not None
                else None
            ),
        }

    def document(self) -> dict[str, object]:
        result = self._result_document(self.latest_result)
        return {
            "task_id": self.task_id,
            "item_id": self.item_id,
            "status": self.status,
            "raw_stage": self.raw_stage,
            "stage": self.stage.value,
            "attempts": self.attempts,
            "source_storage_id": self.source_storage_id,
            "resource_library_id": self.resource_library_id,
            "source_path": self.source_path,
            "plan_id": self.plan_id,
            "destination_storage_id": self.destination_storage_id,
            "destination_path": self.destination_path,
            "configuration": {
                "snapshot_id": self.configuration.snapshot_id,
                "snapshot_digest": self.configuration.snapshot_digest,
                "resolvable": self.configuration.resolvable,
                "reason": self.configuration.reason,
            },
            "latest_result": result,
            "prior_results": [self._result_document(value) for value in self.prior_results],
            "blockers": [self._blocker_document(value) for value in self.blockers],
            "blocker": self._blocker_document(self.blocker) if self.blocker else None,
            "audits": [
                {
                    "audit_id": value.audit_id,
                    "kind": value.kind,
                    "occurred_at": value.occurred_at.isoformat(),
                    "actor": value.actor,
                }
                for value in self.audits
            ],
            "recovery_requests": [value.document() for value in self.recovery_requests],
            "recovery_request": (
                self.active_recovery_request.document()
                if self.active_recovery_request is not None
                else None
            ),
            "recovery_continuation": (
                self.recovery_continuation.document()
                if self.recovery_continuation is not None
                else None
            ),
            "effects": {
                "certainty": self.effect_certainty.value,
                "completed_operations": list(self.completed_operations),
                "uncertain_effects": list(self.uncertain_effects),
            },
            "error_category": self.error_category.value,
            "failureExplanation": self.failure.document() if self.failure else None,
            "nextAction": self.failure.next_action if self.failure else None,
            "retry_safety": self.retry_safety.value,
            "actions": [
                {
                    "action_id": value.action_id,
                    "label": value.label,
                    "confirmation_required": value.confirmation_required,
                    "required_authority": value.required_authority,
                    "resolution_surface": value.resolution_surface,
                    "admissible": value.admissible,
                }
                for value in self.actions
            ],
            "permitted_action_ids": list(self.permitted_action_ids),
            "refusal_reason": self.refusal_reason,
            "checkpoint_version": self.checkpoint_version,
            "updated_at": self.updated_at.isoformat(),
        }

    @staticmethod
    def _blocker_document(value: CheckpointBlocker | None) -> dict[str, object] | None:
        if value is None:
            return None
        return {
            "kind": value.kind,
            "id": value.blocker_id,
            "status": value.status,
            "task_id": value.task_id,
            "item_id": value.item_id,
            "resolution_path": value.resolution_path,
        }

    @staticmethod
    def _result_document(value: CheckpointResult | None) -> dict[str, object] | None:
        if value is None:
            return None
        return {
            "result_id": value.result_id,
            "status": value.status,
            "created_at": value.created_at.isoformat(),
            "recognition_type": value.recognition_type,
            "provider": value.provider,
            "provider_id": value.provider_id,
            "metadata_policy_id": value.metadata_policy_id,
            "naming_policy_id": value.naming_policy_id,
            "classification_policy_id": value.classification_policy_id,
            "organize_policy_id": value.organize_policy_id,
            "operation": value.operation,
            "destination_storage_id": value.destination_storage_id,
            "destination_path": value.destination_path,
            "completed_operations": list(value.completed_operations),
            "effect_certainty": value.effect_certainty.value,
            "uncertain_effects": list(value.uncertain_effects),
            "error_category": value.error_category.value,
            "retry_attempts": value.retry_attempts,
            "cleanup_status": value.cleanup_status,
            "failureExplanation": value.failure.document() if value.failure else None,
        }


# Compatibility aliases keep the public vocabulary discoverable without introducing parallel
# models.  The canonical names above are used internally.
CheckpointProjection = ProcessingCheckpoint
ProcessingStage = CheckpointStage
