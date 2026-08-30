"""Durable bounded batch recovery contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class RecoveryBatchItemStatus(StrEnum):
    SELECTED = "selected"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUSED = "refused"
    WAITING = "waiting"
    UNCHANGED = "unchanged"


class RecoveryBatchStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class RecoveryBatchItem:
    batch_item_id: str
    batch_id: str
    source_task_id: str
    source_item_id: str
    checkpoint_version: str
    status: RecoveryBatchItemStatus
    created_at: datetime
    updated_at: datetime
    request_id: str | None = None
    continuation_id: str | None = None
    job_id: str | None = None
    reason: str | None = None
    error: str | None = None
    next_action: str | None = None

    def document(self) -> dict[str, object]:
        return {
            "batch_item_id": self.batch_item_id,
            "batch_id": self.batch_id,
            "source_task_id": self.source_task_id,
            "source_item_id": self.source_item_id,
            "checkpoint_version": self.checkpoint_version,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "request_id": self.request_id,
            "continuation_id": self.continuation_id,
            "job_id": self.job_id,
            "reason": self.reason,
            "error": self.error,
            "next_action": self.next_action or "inspect this item's checkpoint",
        }


@dataclass(frozen=True)
class RecoveryBatch:
    batch_id: str
    source_task_id: str
    actor: str
    created_at: datetime
    updated_at: datetime
    status: RecoveryBatchStatus
    items: tuple[RecoveryBatchItem, ...]
    unchanged_count: int = 0

    @property
    def selected_count(self) -> int:
        return len(self.items)

    @property
    def counts(self) -> dict[str, int]:
        values = {status.value: 0 for status in RecoveryBatchItemStatus}
        for item in self.items:
            values[item.status.value] += 1
        values["unchanged"] = self.unchanged_count
        return values

    @staticmethod
    def derive_status(items: tuple[RecoveryBatchItem, ...]) -> RecoveryBatchStatus:
        statuses = {item.status for item in items}
        if any(status is RecoveryBatchItemStatus.RUNNING for status in statuses):
            return RecoveryBatchStatus.RUNNING
        if any(status is RecoveryBatchItemStatus.QUEUED for status in statuses):
            return RecoveryBatchStatus.QUEUED
        if any(
            status in {RecoveryBatchItemStatus.WAITING, RecoveryBatchItemStatus.SELECTED}
            for status in statuses
        ):
            return RecoveryBatchStatus.PARTIAL
        if statuses and statuses <= {RecoveryBatchItemStatus.CANCELLED}:
            return RecoveryBatchStatus.CANCELLED
        if statuses and statuses <= {RecoveryBatchItemStatus.FAILED}:
            return RecoveryBatchStatus.FAILED
        if any(
            status
            in {
                RecoveryBatchItemStatus.FAILED,
                RecoveryBatchItemStatus.CANCELLED,
                RecoveryBatchItemStatus.REFUSED,
                RecoveryBatchItemStatus.UNCHANGED,
            }
            for status in statuses
        ):
            return RecoveryBatchStatus.PARTIAL
        return RecoveryBatchStatus.COMPLETED

    def document(self) -> dict[str, object]:
        return {
            "batch_id": self.batch_id,
            "source_task_id": self.source_task_id,
            "actor": self.actor,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "selected_count": self.selected_count,
            "unchanged_count": self.unchanged_count,
            "counts": self.counts,
            "items": [item.document() for item in self.items],
            "next_action": (
                "inspect each item outcome and continue only items with an offered action"
                if self.status is not RecoveryBatchStatus.COMPLETED
                else "inspect the linked DryRun Tasks and Results"
            ),
        }
