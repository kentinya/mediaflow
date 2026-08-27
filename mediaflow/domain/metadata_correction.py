from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from mediaflow.domain.automation import AutomationJob
from mediaflow.domain.task_persistence import PersistentTaskItem


class MetadataCorrectionStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class MetadataCorrectionContinuationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class MetadataCorrectionReview:
    review_id: str
    task_id: str
    item_id: str
    source_storage_id: str
    source_path: str
    recognition_type: str
    metadata_policy_id: str
    provider_id: str
    original_query: str
    original_year: int | None
    original_media_type: str
    outcome: str
    status: MetadataCorrectionStatus
    created_at: datetime
    updated_at: datetime
    corrected_query: str | None = None
    corrected_year: int | None = None
    corrected_media_type: str | None = None
    direct_provider_id: str | None = None
    decided_at: datetime | None = None
    actor: str | None = None


@dataclass(frozen=True)
class MetadataCorrectionDecisionAudit:
    audit_id: str
    review_id: str
    corrected_query: str | None
    corrected_year: int | None
    corrected_media_type: str
    direct_provider_id: str | None
    decided_at: datetime
    actor: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class MetadataCorrectionBatchResolveRequest:
    review: MetadataCorrectionReview
    audit: MetadataCorrectionDecisionAudit
    item: PersistentTaskItem


@dataclass(frozen=True)
class MetadataCorrectionSelection:
    recognition_type: str
    metadata_policy_id: str
    provider: str
    query: str | None
    year: int | None
    media_type: str
    provider_id: str | None = None


@dataclass(frozen=True)
class MetadataCorrectionContinuation:
    """One durable DryRun-only continuation for an immutable File correction."""

    continuation_id: str
    file_id: str
    review_id: str
    source_task_id: str
    source_item_id: str
    configuration_snapshot_id: str
    configuration_snapshot_digest: str
    correction_version: str
    status: MetadataCorrectionContinuationStatus
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


class MetadataCorrectionRepository(Protocol):
    def create_metadata_correction(
        self, review: MetadataCorrectionReview, item: PersistentTaskItem
    ) -> None: ...
    def get_metadata_correction(self, review_id: str) -> MetadataCorrectionReview | None: ...
    def get_metadata_correction_for_item(self, item_id: str) -> MetadataCorrectionReview | None: ...
    def list_metadata_corrections(
        self, *, limit: int = 100
    ) -> tuple[MetadataCorrectionReview, ...]: ...
    def list_pending_metadata_corrections(
        self, *, limit: int = 100, task_id: str | None = None
    ) -> tuple[MetadataCorrectionReview, ...]: ...
    def resolve_metadata_correction(
        self,
        review: MetadataCorrectionReview,
        audit: MetadataCorrectionDecisionAudit,
        item: PersistentTaskItem,
    ) -> None: ...
    def resolve_metadata_corrections_batch(
        self, requests: tuple[MetadataCorrectionBatchResolveRequest, ...]
    ) -> None: ...
    def list_metadata_correction_audit(
        self, review_id: str
    ) -> tuple[MetadataCorrectionDecisionAudit, ...]: ...
    def get_metadata_correction_continuation_for_review(
        self, review_id: str
    ) -> MetadataCorrectionContinuation | None: ...
    def get_metadata_correction_continuation_for_job(
        self, job_id: str
    ) -> MetadataCorrectionContinuation | None: ...
    def admit_metadata_correction_continuation(
        self,
        job: AutomationJob,
        continuation: MetadataCorrectionContinuation,
        *,
        maximum_active_jobs: int,
    ) -> tuple[MetadataCorrectionContinuation, bool]: ...
    def mark_metadata_correction_continuation_running(
        self, job_id: str, now: datetime | None = None
    ) -> MetadataCorrectionContinuation: ...
    def bind_metadata_correction_continuation_task(
        self, job_id: str, task_id: str
    ) -> MetadataCorrectionContinuation: ...
    def complete_metadata_correction_continuation(
        self,
        job_id: str,
        *,
        new_task_id: str | None = None,
        new_result_id: str | None = None,
        success: bool,
        error: str | None = None,
        recovery: str | None = None,
        now: datetime | None = None,
    ) -> MetadataCorrectionContinuation: ...
    def fail_queued_metadata_correction_continuation(
        self,
        job_id: str,
        *,
        error: str,
        recovery: str,
        now: datetime | None = None,
    ) -> MetadataCorrectionContinuation: ...
    def cancel_metadata_correction_continuation(
        self, job_id: str, *, now: datetime | None = None
    ) -> MetadataCorrectionContinuation: ...
