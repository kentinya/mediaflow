from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from mediaflow.domain.task_persistence import PersistentTaskItem


class MetadataReviewStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    IGNORED = "ignored"


@dataclass(frozen=True)
class MetadataReviewScoreComponent:
    name: str
    score: float
    reason: str


@dataclass(frozen=True)
class MetadataReviewCandidate:
    review_id: str
    rank: int
    provider: str
    provider_id: str
    media_type: str
    title: str
    original_title: str | None
    canonical_year: int | None
    regional_year: int | None
    total_score: float
    matched_provider_title: str | None
    matched_title_source: str | None
    score_components: tuple[MetadataReviewScoreComponent, ...] = ()


@dataclass(frozen=True)
class MetadataReview:
    review_id: str
    task_id: str
    item_id: str
    source_storage_id: str
    source_path: str
    recognition_type: str
    metadata_policy_id: str
    query: str
    outcome: str
    status: MetadataReviewStatus
    created_at: datetime
    updated_at: datetime
    selected_rank: int | None = None
    selected_provider: str | None = None
    selected_provider_id: str | None = None
    selected_media_type: str | None = None
    decided_at: datetime | None = None
    actor: str | None = None


@dataclass(frozen=True)
class MetadataReviewDecisionAudit:
    audit_id: str
    review_id: str
    selected_rank: int
    provider: str
    provider_id: str
    media_type: str
    decided_at: datetime
    actor: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class MetadataReviewBatchResolveRequest:
    review: MetadataReview
    audit: MetadataReviewDecisionAudit
    item: PersistentTaskItem


@dataclass(frozen=True)
class MetadataSelection:
    recognition_type: str
    metadata_policy_id: str
    provider: str
    provider_id: str
    media_type: str


class MetadataReviewRepository(Protocol):
    def create_metadata_review(
        self,
        review: MetadataReview,
        candidates: tuple[MetadataReviewCandidate, ...],
        item: PersistentTaskItem,
    ) -> None: ...

    def get_metadata_review(self, review_id: str) -> MetadataReview | None: ...
    def get_metadata_review_for_item(self, item_id: str) -> MetadataReview | None: ...
    def list_metadata_reviews(self, *, limit: int = 100) -> tuple[MetadataReview, ...]: ...
    def list_pending_metadata_reviews(
        self, *, limit: int = 100, task_id: str | None = None
    ) -> tuple[MetadataReview, ...]: ...
    def list_metadata_review_candidates(
        self, review_id: str
    ) -> tuple[MetadataReviewCandidate, ...]: ...
    def resolve_metadata_review(
        self,
        review: MetadataReview,
        audit: MetadataReviewDecisionAudit,
        item: PersistentTaskItem,
    ) -> None: ...
    def resolve_metadata_reviews_batch(
        self, requests: tuple[MetadataReviewBatchResolveRequest, ...]
    ) -> None: ...
    def list_metadata_review_audit(
        self, review_id: str
    ) -> tuple[MetadataReviewDecisionAudit, ...]: ...
