from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from mediaflow.domain.task_persistence import PersistentTaskItem


class MetadataCorrectionStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    IGNORED = "ignored"


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
class MetadataCorrectionSelection:
    recognition_type: str
    metadata_policy_id: str
    provider: str
    query: str | None
    year: int | None
    media_type: str
    provider_id: str | None = None


class MetadataCorrectionRepository(Protocol):
    def create_metadata_correction(
        self, review: MetadataCorrectionReview, item: PersistentTaskItem
    ) -> None: ...
    def get_metadata_correction(self, review_id: str) -> MetadataCorrectionReview | None: ...
    def get_metadata_correction_for_item(self, item_id: str) -> MetadataCorrectionReview | None: ...
    def list_metadata_corrections(
        self, *, limit: int = 100
    ) -> tuple[MetadataCorrectionReview, ...]: ...
    def resolve_metadata_correction(
        self,
        review: MetadataCorrectionReview,
        audit: MetadataCorrectionDecisionAudit,
        item: PersistentTaskItem,
    ) -> None: ...
    def list_metadata_correction_audit(
        self, review_id: str
    ) -> tuple[MetadataCorrectionDecisionAudit, ...]: ...
