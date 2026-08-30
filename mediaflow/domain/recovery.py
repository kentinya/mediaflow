"""Version-bound, non-executing recovery admission contracts.

Recovery admission records an operator's decision to continue a single TaskItem.  The
record is deliberately separate from Task/TaskItem execution state: creating one never
creates work, grants media authority, or invokes a Storage/Provider boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class RecoveryRequestStatus(StrEnum):
    """Durable state for an admitted request (only pending is active in this Task)."""

    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

    @property
    def active(self) -> bool:
        return self is self.PENDING


class RecoveryAdmissionReason(StrEnum):
    ACTION_NOT_PERMITTED = "action_not_permitted"
    STALE_CHECKPOINT = "stale_checkpoint"
    DUPLICATE_ACTIVE_REQUEST = "duplicate_active_request"
    SNAPSHOT_UNAVAILABLE = "snapshot_unavailable"
    INSUFFICIENT_AUTHORITY = "insufficient_authority"
    UNKNOWN_ITEM = "unknown_item"
    ITEM_TASK_MISMATCH = "item_task_mismatch"
    INVALID_ACTION = "invalid_action"
    INVALID_VERSION = "invalid_checkpoint_version"
    INVALID_INPUT = "invalid_input"
    REVIEW_NOT_PENDING = "review_not_pending"
    ATOMIC_COMMIT_FAILED = "atomic_commit_failed"


# The longer name is useful at call sites while the shorter alias keeps the transport
# vocabulary discoverable for integrations that call these rejection reasons directly.
RecoveryRejectionReason = RecoveryAdmissionReason


class RecoveryAdmissionError(ValueError):
    """A bounded, auditable refusal from the shared admission gate."""

    def __init__(
        self,
        reason: RecoveryAdmissionReason,
        message: str,
        *,
        current_checkpoint_version: str | None = None,
        existing_request: RecoveryRequest | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = RecoveryAdmissionReason(reason)
        self.current_checkpoint_version = current_checkpoint_version
        self.existing_request = existing_request


@dataclass(frozen=True)
class RecoveryRequest:
    """One admitted, version-bound request with no execution authority."""

    request_id: str
    task_id: str
    item_id: str
    action_id: str
    checkpoint_version: str
    source_storage_id: str
    source_path: str
    configuration_snapshot_id: str | None
    configuration_snapshot_digest: str | None
    actor: str
    requested_at: datetime
    status: RecoveryRequestStatus = RecoveryRequestStatus.PENDING
    note: str | None = None
    authority_statement: str = (
        "no execute authority; no overwrite authority; no delete authority; "
        "no source-cleanup authority; no rollback authority"
    )
    next_action: str = "inspect the admitted request and wait for the supported recovery path"
    review_kind: str | None = None
    review_id: str | None = None

    @property
    def active(self) -> bool:
        return self.status.active

    def document(self) -> dict[str, object]:
        """Return a bounded transport-safe representation."""

        return {
            "request_id": self.request_id,
            "task_id": self.task_id,
            "item_id": self.item_id,
            "action_id": self.action_id,
            "checkpoint_version": self.checkpoint_version,
            "source_storage_id": self.source_storage_id,
            "source_path": self.source_path,
            "configuration_snapshot_id": self.configuration_snapshot_id,
            "configuration_snapshot_digest": self.configuration_snapshot_digest,
            "actor": self.actor,
            "requested_at": self.requested_at.isoformat(),
            "status": self.status.value,
            "note": self.note,
            "authority_statement": self.authority_statement,
            "next_action": self.next_action,
            "review_kind": self.review_kind,
            "review_id": self.review_id,
        }


class RecoveryRequestRepository(Protocol):
    def list_recovery_requests(
        self, item_id: str, *, limit: int = 32
    ) -> tuple[RecoveryRequest, ...]: ...

    def get_active_recovery_request(self, item_id: str) -> RecoveryRequest | None: ...
